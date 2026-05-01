#!/usr/bin/env python3
"""Post pinned-style top comment on trader video via YouTube Data API.

API can insert comments. It CANNOT pin them — pinning requires Studio DOM.
We'll handle pinning separately if needed.
"""
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_PATH = "/opt/youtube-agent/channel2_token.json"
VIDEO_ID = "qCMw459zFhY"

COMMENT = (
    "Quick aside for anyone running a YouTube channel that uses AI in any part of the workflow:\n\n"
    "YouTube's been quietly terminating \"inauthentic content\" channels with very specific signals "
    "- repeated title templates, boilerplate descriptions, near-identical durations, mechanical posting cadence.\n\n"
    "I built a free scanner that checks any channel for those signals so you can spot the pattern "
    "before YouTube's classifier does.\n\n"
    "https://theoperatorai.io/tool/channelguard/\n\n"
    "No signup, no email, takes 5 seconds. Curious what your score is - drop it below."
)


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

    existing = yt.commentThreads().list(
        part="snippet", videoId=VIDEO_ID, maxResults=100, textFormat="plainText"
    ).execute()
    for item in existing.get("items", []):
        text = item["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
        if "channelguard" in text.lower():
            print(f"ALREADY POSTED (commentThreadId={item['id']})")
            return 0

    try:
        res = yt.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": VIDEO_ID,
                    "topLevelComment": {
                        "snippet": {"textOriginal": COMMENT}
                    }
                }
            }
        ).execute()
        cid = res["id"]
        print(f"OK posted commentThreadId={cid}")
        return 0
    except HttpError as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
