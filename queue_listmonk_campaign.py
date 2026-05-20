#!/usr/bin/env python3
"""Create the ChannelGuard promotional campaign as a Listmonk draft.

Leaves it in 'draft' state for manual start from the Listmonk admin
(consistent with the existing newsletter approval gate). Outputs the campaign
ID + admin URL.
"""
import sys
sys.path.insert(0, "/opt/agent-common")
from listmonk_api import create_campaign

SUBJECT = "I wrote up the 5 patterns YouTube is flagging right now"

BODY_HTML = """<p>YouTube's been terminating AI-assisted channels under its "inauthentic content" policy at a pace that's spooking everyone running automated workflows.</p>

<p>I spent the last week reverse-engineering the public-facing cases. Five patterns kept showing up. None individually fatal, but channels hitting three or more are the ones getting hit.</p>

<p>Wrote the full breakdown here, including how to check each one manually:<br>
<a href="https://theoperatorai.io/articles/youtube-channel-termination-5-patterns.html">theoperatorai.io/articles/youtube-channel-termination-5-patterns</a></p>

<p>The article has a free scanner at the bottom that automates checking all five against your channel &mdash; paste a URL, get a risk score in 5 seconds, no signup.</p>

<p>If you've got a channel &mdash; yours, a friend's, a competitor's &mdash; give it a run and tell me what you see.</p>

<p>&mdash; TheOperatorAI</p>
"""


def main():
    campaign = create_campaign(
        subject=SUBJECT,
        html_body=BODY_HTML,
        content_type="richtext",
        tags=["channelguard", "promo"],
    )
    cid = campaign["id"]
    print(f"Campaign created: id={cid}")
    print(f"Status: {campaign.get('status', 'draft')}")
    print(f"Admin URL: https://newsletter.theoperatorai.io/admin/campaigns/{cid}")
    print()
    print("To send: open the URL above, click Start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
