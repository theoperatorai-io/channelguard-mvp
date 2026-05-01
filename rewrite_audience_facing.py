#!/usr/bin/env python3
"""Rewrite audience-facing copy to remove AI tells.

1. Update trader video pinned comment via YouTube Data API
2. Replace the ChannelGuard footer in the trader video description
3. Update the queued Buffer X post (or delete + replace if update unavailable)
"""
import json
import os
import sys
import urllib.request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "/opt/youtube-agent/channel2_token.json"
VIDEO_ID = "qCMw459zFhY"
COMMENT_THREAD_ID = "UgwInJQjh7l9kU52mQJ4AaABAg"
BUFFER_POST_ID = "69f3be26c071eb210ff218ec"

NEW_COMMENT = (
    "Quick note if you run a YouTube channel that uses AI anywhere in your workflow.\n\n"
    "YouTube's been quietly terminating \"inauthentic content\" channels lately. "
    "I looked at a bunch of public takedown cases and the common thread isn't \"uses AI\" by itself. "
    "It's a stack of signals showing up together: title templates that repeat, descriptions with the "
    "same first paragraph every video, near-identical video durations, uploads on a perfectly regular schedule.\n\n"
    "Built a free scanner that checks your channel for that pattern so you can spot it before "
    "YouTube's classifier does.\n\n"
    "https://theoperatorai.io/tool/channelguard/\n\n"
    "No signup, no email, takes 5 seconds. Drop your score below if you try it."
)

OLD_FOOTER_MARKER = "Worried about YouTube's inauthentic-content takedowns"
NEW_FOOTER = (
    "\n\n---\n"
    "Worried about getting hit by YouTube's \"inauthentic content\" terminations? "
    "Built a free scanner that checks your channel for the patterns they're targeting. No signup needed.\n"
    "https://theoperatorai.io/tool/channelguard/"
)

NEW_TWEET = (
    "looked at every public YouTube channel termination under the new \"inauthentic content\" rule.\n\n"
    "pattern: repeating title templates, boilerplate descriptions, identical video lengths, "
    "cron-like cadence, new channels pushing 5+/week.\n\n"
    "free scanner + writeup:\n"
    "theoperatorai.io/articles/youtube-channel-termination-5-patterns"
)


def load_yt_creds():
    data = json.load(open(TOKEN_PATH))
    creds = Credentials(
        token=data["token"], refresh_token=data["refresh_token"],
        token_uri=data["token_uri"], client_id=data["client_id"],
        client_secret=data["client_secret"], scopes=data["scopes"],
    )
    if not creds.valid:
        creds.refresh(Request())
        json.dump({**data, "token": creds.token,
                  "expiry": creds.expiry.isoformat() if creds.expiry else None},
                 open(TOKEN_PATH, "w"))
    return creds


def update_comment(yt):
    print("\n=== 1. UPDATE YOUTUBE COMMENT ===")
    res = yt.commentThreads().list(
        part="snippet,id", id=COMMENT_THREAD_ID
    ).execute()
    if not res.get("items"):
        print("FAIL: comment thread not found")
        return
    top = res["items"][0]["snippet"]["topLevelComment"]
    comment_id = top["id"]
    print(f"comment_id: {comment_id}")
    print(f"old text head: {top['snippet']['textOriginal'][:80]}")
    upd = yt.comments().update(
        part="snippet",
        body={"id": comment_id, "snippet": {"textOriginal": NEW_COMMENT}}
    ).execute()
    print(f"updated. new text head: {upd['snippet']['textOriginal'][:80]}")


def update_description(yt):
    print("\n=== 2. UPDATE TRADER VIDEO DESCRIPTION ===")
    res = yt.videos().list(part="snippet", id=VIDEO_ID).execute()
    snippet = res["items"][0]["snippet"]
    desc = snippet["description"]
    idx = desc.find("---\nWorried about")
    if idx == -1:
        print("FAIL: old footer marker not found")
        return
    new_desc = desc[:idx].rstrip() + NEW_FOOTER
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
    print(f"desc len: {len(desc)} -> {len(upd['snippet']['description'])}")


def update_buffer_post():
    print("\n=== 3. UPDATE BUFFER X POST ===")
    key = os.environ["BUFFER_API_KEY"]

    # Try updatePost mutation first
    upd_query = """
    mutation UpdatePost($input: UpdatePostInput!) {
      updatePost(input: $input) {
        ... on PostActionSuccess { post { id text } }
        ... on InvalidInputError { message }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on MutationError { message }
      }
    }
    """
    body = json.dumps({
        "query": upd_query,
        "variables": {"input": {"id": BUFFER_POST_ID, "text": NEW_TWEET}},
    }).encode()
    req = urllib.request.Request(
        "https://api.buffer.com",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print("update response:", json.dumps(resp, indent=2)[:500])
        if "errors" in resp:
            print("update failed; falling back to delete+create")
            return delete_and_create_buffer(key)
        return
    except Exception as e:
        print(f"update threw: {e}")
        return delete_and_create_buffer(key)


def delete_and_create_buffer(key):
    print("=== 3b. DELETE + CREATE BUFFER POST ===")
    del_query = """
    mutation DeletePost($input: DeletePostInput!) {
      deletePost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on MutationError { message }
      }
    }
    """
    body = json.dumps({
        "query": del_query,
        "variables": {"input": {"id": BUFFER_POST_ID}},
    }).encode()
    req = urllib.request.Request(
        "https://api.buffer.com",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print("delete:", json.dumps(resp)[:300])
    except Exception as e:
        print(f"delete failed: {e}")

    create_query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text } }
        ... on InvalidInputError { message }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on MutationError { message }
      }
    }
    """
    body = json.dumps({
        "query": create_query,
        "variables": {"input": {
            "channelId": "69b22d577be9f8b171490693",
            "text": NEW_TWEET,
            "schedulingType": "automatic",
            "mode": "addToQueue",
        }},
    }).encode()
    req = urllib.request.Request(
        "https://api.buffer.com",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print("create:", json.dumps(resp)[:400])


def main():
    yt = build("youtube", "v3", credentials=load_yt_creds())
    update_comment(yt)
    update_description(yt)
    update_buffer_post()


if __name__ == "__main__":
    main()
