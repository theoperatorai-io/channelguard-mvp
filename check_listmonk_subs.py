#!/usr/bin/env python3
import sys
sys.path.insert(0, "/opt/agent-common")
from listmonk_api import _api

lists = _api("GET", "/api/lists")["data"]
print("=== Lists ===")
items = lists.get("results", lists if isinstance(lists, list) else [])
for l in items:
    print("  id={} name={!r} subs={} optin={}".format(
        l["id"], l["name"], l.get("subscriber_count", "?"), l.get("optin")))

print("\n=== List 4 subscribers ===")
res = _api("GET", "/api/subscribers?list_id=4&per_page=50")["data"]
print("total:", res.get("total"))
for s in res.get("results", [])[:15]:
    print("  {}  {}  status={}  list_status={}".format(
        s["id"], s["email"], s["status"],
        next((ls.get("subscription_status") for ls in s.get("lists", []) if ls.get("id") == 4), "?")))

print("\n=== Campaign 39 ===")
c = _api("GET", "/api/campaigns/39")["data"]
for k in ("status", "to_send", "sent", "started_at", "from_email"):
    print(f"  {k}: {c.get(k)}")
