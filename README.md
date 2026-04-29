# ChannelGuard

Free YouTube channel risk scanner — detects inauthentic-content patterns YouTube's automated systems use to flag and terminate channels.

**Live:** https://theoperatorai.io/tool/channelguard/

## Architecture

- **Backend:** Python aiohttp service on VPS at `127.0.0.1:8012`
- **Frontend:** Static HTML/CSS/JS at `/var/www/html/tool/channelguard/`
- **nginx:** Reverse-proxies `/api/channelguard/*` to the backend
- **Storage:** SQLite at `/opt/channelguard/scans.db` (scans + waitlist)
- **Email capture:** Listmonk via `/opt/agent-common/listmonk_api.py`
- **YouTube data:** YouTube Data API v3

## Risk signals (v1)

1. Upload cadence (avg gap between uploads)
2. Title template repetition (first 3 words match across recent videos)
3. Description boilerplate (first 200 chars identical)
4. Channel age vs upload count (young channels with burst uploads)
5. Duration uniformity (videos within 30s of same length)

## Deploy

Files in this repo mirror the VPS layout:

| Repo path | VPS path |
|---|---|
| `server.py` | `/opt/channelguard/server.py` |
| `public/index.html` | `/var/www/html/tool/channelguard/index.html` |
| `nginx_patch.py` | one-time patcher for `/etc/nginx/sites-enabled/theoperatorai` |

Service: `systemctl {start,stop,restart,status} channelguard`
