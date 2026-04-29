#!/usr/bin/env python3
"""Patch the theoperatorai nginx config to add a /api/channelguard/ reverse-proxy block."""
import sys

CONF = "/etc/nginx/sites-enabled/theoperatorai"
ANCHOR = "    # Stack recommender backend"
BLOCK = """    # ChannelGuard backend (added 2026-04-29)
    location /api/channelguard/ {
        proxy_pass http://127.0.0.1:8012;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

"""

s = open(CONF).read()
if "channelguard" in s:
    print("Already patched, exiting clean.")
    sys.exit(0)
if ANCHOR not in s:
    print(f"ERROR: anchor not found: {ANCHOR}")
    sys.exit(1)
new = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
open(CONF, "w").write(new)
print("OK: nginx block added")
