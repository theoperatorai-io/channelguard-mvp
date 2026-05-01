#!/usr/bin/env python3
"""Send a test campaign to verify Listmonk SMTP is working after App Password reset."""
import sys
import time
sys.path.insert(0, "/opt/agent-common")
from listmonk_api import _api, create_campaign, start_campaign

camp = create_campaign(
    subject="[SMTP TEST] Listmonk delivery check",
    html_body=(
        "<p>If you see this in your inbox, Listmonk SMTP is working again "
        "after the App Password reset.</p><p>You can delete this.</p>"
    ),
    content_type="richtext",
    tags=["smtp-test"],
)
cid = camp["id"]
print("Test campaign created: id=" + str(cid))
print("Starting...")
start_campaign(cid)

time.sleep(8)
c = _api("GET", f"/api/campaigns/{cid}")["data"]
print("status:", c["status"])
print("to_send:", c["to_send"])
print("sent:", c["sent"])
