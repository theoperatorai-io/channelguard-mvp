#!/usr/bin/env python3
"""Post the ChannelGuard organic tweet via Buffer API as a one-off.

Sits alongside the daily AI-tip cron — does NOT touch pending_tweets.json or
that pipeline. Pushes directly to Buffer queue with mode=addToQueue.
"""
import asyncio
import os
import sys
import aiohttp

BUFFER_API_URL = "https://api.buffer.com"
BUFFER_CHANNEL_ID = "69b22d577be9f8b171490693"
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

TWEET = (
    "YouTube's terminating \"inauthentic content\" channels for 5 signals:\n\n"
    "→ repeated title templates\n"
    "→ boilerplate descriptions\n"
    "→ near-uniform durations\n"
    "→ mechanical posting cadence\n"
    "→ new channels uploading too fast\n\n"
    "Free scanner + breakdown:\n"
    "theoperatorai.io/articles/youtube-channel-termination-5-patterns"
)


async def main():
    print(f"len: {len(TWEET)} chars")
    if len(TWEET) > 280:
        print("WARN: tweet over 280 chars — Buffer may reject for X")

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text } }
        ... on LimitReachedError { message }
        ... on InvalidInputError { message }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on RestProxyError { message code }
        ... on MutationError { message }
      }
    }
    """
    variables = {
        "input": {
            "channelId": BUFFER_CHANNEL_ID,
            "text": TWEET,
            "schedulingType": "automatic",
            "mode": "addToQueue",
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BUFFER_API_URL,
            headers={"Authorization": f"Bearer {BUFFER_API_KEY}",
                     "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            data = await r.json()
            print("RESPONSE:", data)
            if "errors" in data or data.get("data", {}).get("createPost", {}).get("message"):
                return 1
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
