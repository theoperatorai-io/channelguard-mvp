#!/usr/bin/env python3
"""Append ChannelGuard CTA footer to trader video description via YouTube Data API."""
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/opt/youtube-agent/channel2_token.json"
VIDEO_ID = "qCMw459zFhY"

APPEND = "\n\n---\nWorried about YouTube's inauthentic-content takedowns hitting your channel? I built a free scanner that checks for the exact patterns being flagged - no signup needed:\nhttps://theoperatorai.io/tool/channelguard/"


def load_creds():
    data = json.load(open(TOKEN_PATH))
    creds = Credentials(
        token=data["token"], refresh_token=data["refresh_token"],
        token_uri=data["token_uri"], client_id=data["client_id"],
        client_secret=data["client_secret"], scopes=data["scopes"],
    )
    if not creds.valid:
        creds.refresh(Request())
        out = {**data, "token": creds.token,
               "expiry": creds.expiry.isoformat() if creds.expiry else None}
        json.dump(out, open(TOKEN_PATH, "w"))
        print("[refreshed token]")
    return creds


def main():
    yt = build("youtube", "v3", credentials=load_creds())
    res = yt.videos().list(part="snippet", id=VIDEO_ID).execute()
    items = res.get("items", [])
    if not items:
        print("NO VIDEO"); return 1
    snippet = items[0]["snippet"]
    print(f"title: {snippet['title'][:70]}")
    print(f"desc len before: {len(snippet['description'])}")
    if "channelguard" in snippet["description"].lower():
        print("ALREADY APPENDED - skipping")
        return 0
    new_desc = snippet["description"] + APPEND
    body = {
        "id": VIDEO_ID,
        "snippet": {
            "title": snippet["title"],
            "description": new_desc,
            "categoryId": snippet["categoryId"],
            "tags": snippet.get("tags", []),
        }
    }
    if snippet.get("defaultLanguage"):
        body["snippet"]["defaultLanguage"] = snippet["defaultLanguage"]
    upd = yt.videos().update(part="snippet", body=body).execute()
    print(f"desc len after: {len(upd['snippet']['description'])}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
