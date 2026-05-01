#!/usr/bin/env python3
"""Pin our ChannelGuard comment on trader video.

Uses the YouTube Studio persistent profile. Pinning is not in the Data API,
so this is DOM-only. Bails cleanly on failure (no risk to profile state).
"""
import asyncio
import os
import pathlib
import sys
from playwright.async_api import async_playwright

PROFILE_DIR = pathlib.Path("/opt/youtube-agent/chromium_profiles/youtube_studio_ch2")
VIDEO_ID = "qCMw459zFhY"
SHOT_DIR = pathlib.Path("/tmp/cg_pin")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")


async def main():
    os.environ.setdefault("DISPLAY", ":99")
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            user_agent=UA,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox", "--no-first-run",
                "--disable-features=TranslateUI",
            ],
        )
        page = await ctx.new_page()

        await page.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2500)

        url = f"https://studio.youtube.com/video/{VIDEO_ID}/comments"
        print(f"nav: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(6000)

        await page.screenshot(path=str(SHOT_DIR / "01_loaded.png"))

        result = await page.evaluate("""
            async () => {
              const wait = ms => new Promise(r => setTimeout(r, ms));
              const all = Array.from(document.querySelectorAll('ytcp-comment-thread, ytcr-comment-thread, ytcp-comment, ytcr-comment'));
              let matched = null;
              for (const el of all) {
                const txt = (el.textContent || '').toLowerCase();
                if (txt.includes('channelguard')) { matched = el; break; }
              }
              if (!matched) return { ok: false, reason: 'comment row not found', candidates: all.length };

              matched.scrollIntoView({ block: 'center' });
              await wait(800);

              const menuBtn = matched.querySelector(
                'ytcp-icon-button#menu-button, button[aria-label*="more" i], button[aria-label*="action" i], yt-icon-button#menu, ytcp-icon-button[aria-label*="action" i]'
              );
              if (!menuBtn) return { ok: false, reason: 'menu button not found in row' };
              menuBtn.click();
              await wait(800);

              const items = Array.from(document.querySelectorAll('tp-yt-paper-listbox tp-yt-paper-item, ytcp-text-menu-item, ytmusic-menu-popup-renderer yt-formatted-string, [role=menuitem]'));
              let pinItem = null;
              for (const it of items) {
                const t = (it.textContent || '').trim().toLowerCase();
                if (t === 'pin' || t.startsWith('pin ')) { pinItem = it; break; }
              }
              if (!pinItem) return { ok: false, reason: 'pin menu item not found', items: items.map(i => (i.textContent||'').trim()).slice(0,10) };
              pinItem.click();
              await wait(1500);

              const dialogBtns = Array.from(document.querySelectorAll('ytcp-button, button'));
              for (const b of dialogBtns) {
                const t = (b.textContent || '').trim().toLowerCase();
                if (t === 'pin' || t === 'confirm') {
                  b.click();
                  await wait(1500);
                  return { ok: true, confirmed: true };
                }
              }
              return { ok: true, confirmed: false, note: 'no confirm dialog appeared' };
            }
        """)

        await page.screenshot(path=str(SHOT_DIR / "02_after.png"))
        print("RESULT:", result)
        await page.wait_for_timeout(2000)
        await ctx.close()
        return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
