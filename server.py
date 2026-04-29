#!/usr/bin/env python3
"""
ChannelGuard - YouTube channel risk scanner.

POST /api/channelguard/scan { channel_url }
   -> JSON { score, findings, channel: {...}, scan_id }

POST /api/channelguard/waitlist { email, scan_id? }
   -> JSON { ok }
"""
import json
import logging
import os
import re
import sys
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from aiohttp import web

sys.path.insert(0, "/opt/agent-common")
from listmonk_api import add_subscriber

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("channelguard")

PORT = 8012
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GEMINI_API_KEY")
DB_PATH = "/opt/channelguard/scans.db"
WAITLIST_LIST_NAME_TAG = "channelguard_waitlist"

YT_API = "https://www.googleapis.com/youtube/v3"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            channel_id TEXT,
            channel_title TEXT,
            input_url TEXT,
            score INTEGER,
            findings_json TEXT,
            ip_hash TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            email TEXT UNIQUE,
            scan_id INTEGER REFERENCES scans(id)
        )
    """)
    conn.commit()
    conn.close()


# ── YouTube channel resolution ─────────────────────────────────────────────

def resolve_channel_id(input_url):
    """Take any YouTube channel URL/handle and return a channel_id."""
    s = input_url.strip()
    if not s:
        return None

    # Handle bare handle like @something
    if s.startswith("@"):
        return _channel_id_from_handle(s)

    # Strip URL bits
    if not s.startswith("http"):
        s = "https://" + s
    parsed = urlparse(s)
    path = parsed.path.strip("/")
    parts = path.split("/")

    if not parts:
        return None

    # /channel/UCxxxx
    if parts[0] == "channel" and len(parts) > 1:
        return parts[1]

    # /@handle
    if parts[0].startswith("@"):
        return _channel_id_from_handle(parts[0])

    # /c/customname or /user/legacyname or bare /something
    name = parts[1] if parts[0] in ("c", "user") and len(parts) > 1 else parts[0]
    if name:
        # Try as handle first (most modern channels)
        cid = _channel_id_from_handle("@" + name)
        if cid:
            return cid
        # Fall back to search
        return _channel_id_from_search(name)

    return None


def _channel_id_from_handle(handle):
    handle = handle.lstrip("@")
    try:
        r = requests.get(
            f"{YT_API}/channels",
            params={"part": "id", "forHandle": "@" + handle, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
        if items:
            return items[0]["id"]
    except Exception as e:
        log.warning("handle resolve failed: %s", e)
    return None


def _channel_id_from_search(query):
    try:
        r = requests.get(
            f"{YT_API}/search",
            params={"part": "snippet", "type": "channel", "q": query, "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
        if items:
            return items[0]["snippet"]["channelId"]
    except Exception as e:
        log.warning("search resolve failed: %s", e)
    return None


def fetch_channel_data(channel_id):
    """Fetch channel snippet + last 50 video IDs + their snippets."""
    # 1. channel info
    r = requests.get(
        f"{YT_API}/channels",
        params={"part": "snippet,statistics,contentDetails", "id": channel_id, "key": YOUTUBE_API_KEY},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        return None
    ch = items[0]
    uploads_playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    # 2. last 50 videos from uploads playlist
    r = requests.get(
        f"{YT_API}/playlistItems",
        params={"part": "snippet,contentDetails", "playlistId": uploads_playlist, "maxResults": 50, "key": YOUTUBE_API_KEY},
        timeout=10,
    )
    r.raise_for_status()
    playlist_items = r.json().get("items") or []
    video_ids = [it["contentDetails"]["videoId"] for it in playlist_items]

    # 3. video details (description, duration)
    videos = []
    if video_ids:
        # one batch call (max 50)
        r = requests.get(
            f"{YT_API}/videos",
            params={"part": "snippet,contentDetails,statistics", "id": ",".join(video_ids), "key": YOUTUBE_API_KEY},
            timeout=15,
        )
        r.raise_for_status()
        videos = r.json().get("items") or []

    return {"channel": ch, "videos": videos}


# ── Risk signals ───────────────────────────────────────────────────────────

def signal_upload_cadence(videos):
    """Avg gap between uploads. <12h is suspicious automation."""
    if len(videos) < 5:
        return None
    timestamps = sorted([v["snippet"]["publishedAt"] for v in videos])
    gaps_hours = []
    for i in range(1, len(timestamps)):
        a = datetime.fromisoformat(timestamps[i-1].replace("Z", "+00:00"))
        b = datetime.fromisoformat(timestamps[i].replace("Z", "+00:00"))
        gaps_hours.append((b - a).total_seconds() / 3600)
    avg_gap = sum(gaps_hours) / len(gaps_hours)

    if avg_gap < 4:
        return {"signal": "upload_cadence", "severity": "high",
                "label": "Extreme upload cadence",
                "detail": f"Average {avg_gap:.1f}h between uploads (humans typically 24h+)"}
    if avg_gap < 12:
        return {"signal": "upload_cadence", "severity": "medium",
                "label": "Heavy upload cadence",
                "detail": f"Average {avg_gap:.1f}h between uploads — pattern suggests automation"}
    if avg_gap < 24:
        return {"signal": "upload_cadence", "severity": "low",
                "label": "High upload frequency",
                "detail": f"Average {avg_gap:.1f}h between uploads — sustainable for humans only with a team"}
    return None


def signal_title_template(videos):
    """Detect repeated title prefixes/suffixes/patterns."""
    if len(videos) < 5:
        return None
    titles = [v["snippet"]["title"] for v in videos]

    # First 3 words match across >=60% of videos
    first_three = [tuple(t.split()[:3]) for t in titles if len(t.split()) >= 3]
    if not first_three:
        return None
    from collections import Counter
    top, count = Counter(first_three).most_common(1)[0]
    pct = count / len(first_three)
    if pct >= 0.6:
        return {"signal": "title_template", "severity": "high",
                "label": "Title template detected",
                "detail": f"{int(pct*100)}% of recent videos start with '{' '.join(top)}...'"}
    if pct >= 0.3:
        return {"signal": "title_template", "severity": "medium",
                "label": "Repeated title pattern",
                "detail": f"{int(pct*100)}% of recent videos start with '{' '.join(top)}...'"}
    return None


def signal_description_boilerplate(videos):
    """First 200 chars of description identical across >=70% of videos."""
    if len(videos) < 5:
        return None
    descs = [(v["snippet"].get("description") or "")[:200] for v in videos]
    descs = [d for d in descs if d.strip()]
    if not descs:
        return None
    from collections import Counter
    top, count = Counter(descs).most_common(1)[0]
    pct = count / len(descs)
    if pct >= 0.7:
        return {"signal": "description_boilerplate", "severity": "medium",
                "label": "Identical description prefix",
                "detail": f"{int(pct*100)}% of videos share the same opening 200 chars (boilerplate)"}
    return None


def signal_channel_age_vs_uploads(channel, videos):
    """Channels <60 days old with >30 uploads = farm pattern."""
    created = channel["snippet"]["publishedAt"]
    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - created_dt).days
    upload_count = int(channel["statistics"].get("videoCount", 0))

    if age_days < 30 and upload_count >= 20:
        return {"signal": "channel_age", "severity": "high",
                "label": "Young channel, very high upload count",
                "detail": f"Channel is {age_days} days old with {upload_count} uploads"}
    if age_days < 90 and upload_count >= 100:
        return {"signal": "channel_age", "severity": "high",
                "label": "Burst-upload pattern",
                "detail": f"{upload_count} uploads in {age_days} days"}
    return None


def signal_duration_uniformity(videos):
    """If most videos are within 30s of the same duration = template format."""
    if len(videos) < 5:
        return None
    import re as _re
    def parse_iso8601_duration(s):
        m = _re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
        if not m:
            return None
        h, m_, s_ = (int(x) if x else 0 for x in m.groups())
        return h * 3600 + m_ * 60 + s_
    durations = [parse_iso8601_duration(v["contentDetails"].get("duration") or "") for v in videos]
    durations = [d for d in durations if d and d > 30]
    if len(durations) < 5:
        return None
    avg = sum(durations) / len(durations)
    within_30s = sum(1 for d in durations if abs(d - avg) <= 30)
    pct = within_30s / len(durations)
    if pct >= 0.7 and avg > 60:
        return {"signal": "duration_uniformity", "severity": "low",
                "label": "Uniform video length",
                "detail": f"{int(pct*100)}% of videos within 30s of {int(avg)}s — template-driven format"}
    return None


SEVERITY_WEIGHT = {"high": 30, "medium": 15, "low": 5}


def score_channel(data):
    findings = []
    sigs = [
        signal_upload_cadence(data["videos"]),
        signal_title_template(data["videos"]),
        signal_description_boilerplate(data["videos"]),
        signal_channel_age_vs_uploads(data["channel"], data["videos"]),
        signal_duration_uniformity(data["videos"]),
    ]
    for s in sigs:
        if s:
            findings.append(s)
    risk = sum(SEVERITY_WEIGHT.get(f["severity"], 0) for f in findings)
    risk = min(risk, 100)
    return risk, findings


# ── HTTP handlers ──────────────────────────────────────────────────────────

async def handle_scan(request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    input_url = (body.get("channel_url") or "").strip()[:300]
    if not input_url:
        return web.json_response({"error": "missing_channel_url"}, status=400)

    if not YOUTUBE_API_KEY:
        return web.json_response({"error": "server_misconfigured"}, status=500)

    log.info("Scan request: %s", input_url[:100])

    channel_id = resolve_channel_id(input_url)
    if not channel_id:
        return web.json_response({
            "error": "channel_not_found",
            "message": "Could not resolve that to a YouTube channel. Try the channel's full URL or @handle.",
        }, status=404)

    try:
        data = fetch_channel_data(channel_id)
    except requests.HTTPError as e:
        log.error("YouTube API error: %s", e.response.text[:300] if e.response else e)
        return web.json_response({"error": "youtube_api_failed"}, status=502)
    except Exception as e:
        log.error("Fetch error: %s", e)
        return web.json_response({"error": "fetch_failed"}, status=502)

    if not data:
        return web.json_response({"error": "channel_not_found"}, status=404)

    score, findings = score_channel(data)

    # Persist scan
    scan_id = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "INSERT INTO scans (ts, channel_id, channel_title, input_url, score, findings_json, ip_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                channel_id,
                data["channel"]["snippet"]["title"],
                input_url,
                score,
                json.dumps(findings),
                "",
            ),
        )
        scan_id = cur.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("DB write failed: %s", e)

    ch = data["channel"]
    return web.json_response({
        "scan_id": scan_id,
        "score": score,
        "findings": findings,
        "channel": {
            "id": channel_id,
            "title": ch["snippet"]["title"],
            "subscriber_count": ch["statistics"].get("subscriberCount", "0"),
            "video_count": ch["statistics"].get("videoCount", "0"),
            "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
            "published_at": ch["snippet"]["publishedAt"],
        },
        "videos_analyzed": len(data["videos"]),
    })


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


async def handle_waitlist(request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    email = (body.get("email") or "").strip().lower()[:200]
    scan_id = body.get("scan_id")

    if not EMAIL_RE.match(email):
        return web.json_response({"error": "invalid_email"}, status=400)

    # Save locally
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO waitlist (ts, email, scan_id) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), email, scan_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("Waitlist DB write failed: %s", e)

    # Push to Listmonk
    try:
        add_subscriber(email, name="", list_ids=None)
    except Exception as e:
        log.warning("Listmonk push failed for %s: %s", email, e)

    log.info("Waitlist signup: %s (scan %s)", email, scan_id)
    return web.json_response({"ok": True})


async def handle_health(request):
    return web.json_response({"ok": True, "yt_key_present": bool(YOUTUBE_API_KEY)})


def main():
    init_db()
    app = web.Application(client_max_size=64 * 1024)
    app.router.add_post("/api/channelguard/scan", handle_scan)
    app.router.add_post("/api/channelguard/waitlist", handle_waitlist)
    app.router.add_get("/api/channelguard/health", handle_health)
    log.info("ChannelGuard listening on 127.0.0.1:%d (yt_key=%s)", PORT, "yes" if YOUTUBE_API_KEY else "MISSING")
    web.run_app(app, host="127.0.0.1", port=PORT, access_log=None)


if __name__ == "__main__":
    main()
