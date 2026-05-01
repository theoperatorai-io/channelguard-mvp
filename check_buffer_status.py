#!/usr/bin/env python3
"""Check status of the ChannelGuard tweet in Buffer."""
import os, json, urllib.request

key = os.environ["BUFFER_API_KEY"]
q = """
query { posts(input: { organizationId: "69b22d305c2bde3cfb7db486", limit: 20 }) {
  edges { node { id text status scheduledAt sentAt } }
}}
"""
req = urllib.request.Request(
    "https://api.buffer.com",
    data=json.dumps({"query": q}).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
)
data = json.loads(urllib.request.urlopen(req, timeout=15).read())
edges = data.get("data", {}).get("posts", {}).get("edges", [])
print(f"Total recent posts: {len(edges)}")
for edge in edges:
    n = edge["node"]
    text = (n.get("text") or "")
    if "channelguard" in text.lower() or "youtube-channel-termination" in text.lower():
        print()
        print("=== Match ===")
        print("  id:", n["id"])
        print("  status:", n["status"])
        print("  scheduledAt:", n.get("scheduledAt"))
        print("  sentAt:", n.get("sentAt"))
        print("  text head:", text[:80].replace("\n", " "))
