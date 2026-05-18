#!/usr/bin/env python3
"""
crawl_course.py — Playwright Chromium with persistent profile.
Login survives browser close. Intercepts all classplus API calls.

Usage:
  python3 crawl_course.py [course_id]
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

COURSE_ID = "696969"
USER_DATA = "/tmp/playwright_classplus_profile"  # persistent — login survives!
OUTPUT = "/tmp/classplus_manifest.json"
SIGNAL_FILE = "/tmp/classplus_done"

captured = {
    "token": None,
    "endpoints": set(),
    "responses": [],
    "folder_api_url": None,
}


async def main():
    course_id = sys.argv[1] if len(sys.argv) > 1 else COURSE_ID

    if os.path.exists(SIGNAL_FILE):
        os.remove(SIGNAL_FILE)

    async with async_playwright() as p:
        # Persistent context — cookies/localStorage saved to disk
        context = await p.chromium.launch_persistent_context(
            USER_DATA,
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ── Network interceptor — only API calls ───────────────────
        async def on_response(response):
            url = response.url
            if "classplusapp.com" not in url:
                return
            path = urlparse(url).path
            captured["endpoints"].add(f"{response.request.method} {path}")

            tok = response.request.headers.get("x-access-token")
            if tok and len(tok) > 50:
                captured["token"] = tok

            try:
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                body = await response.json()
                if isinstance(body, dict):
                    keys = list(body.keys())
                    captured["responses"].append({
                        "url": url, "path": path,
                        "status": response.status, "keys": keys,
                    })
                    interesting = {"data", "content", "items", "videos",
                                   "folders", "batchContent", "courses", "lectures"}
                    if interesting & set(keys):
                        print(f"\n  API: {path}  keys={keys}")
                        fname = f"/tmp/classplus_api_{path.replace('/','_').strip('_')}.json"
                        with open(fname, "w") as f:
                            json.dump(body, f, indent=2, default=str)
            except Exception:
                pass

        page.on("response", on_response)

        # ── Navigate ──────────────────────────────────────────────
        course_url = f"https://web.classplusapp.com/store/course/{course_id}/0?section=content"
        print(f"Opening: {course_url}")
        try:
            await page.goto(course_url, wait_until="load", timeout=60000)
        except Exception as e:
            print(f"  (page may need login: {e})")

        await asyncio.sleep(2)

        # Extract localStorage token
        try:
            tok = await page.evaluate("""
                for (const k of ['token','accessToken','x-access-token','jwt','auth']) {
                    const v = localStorage.getItem(k);
                    if (v && v.startsWith('eyJ')) return v;
                }
                return null;
            """)
            if tok:
                captured["token"] = tok
                print(f"\n[+] localStorage token found (len={len(tok)})")
        except Exception:
            pass

        # ── Wait for user to explore ──────────────────────────────
        print("\n" + "=" * 60)
        print("  BROWSER IS OPEN (persistent profile — login survives!)")
        print(f"  Profile: {USER_DATA}")
        print()
        print("  1. Log in (if needed)")
        print("  2. Navigate folders, click videos")
        print(f"  3. From another terminal:  touch {SIGNAL_FILE}")
        print("     Or just close the browser window")
        print("=" * 60)

        while True:
            await asyncio.sleep(0.5)
            if os.path.exists(SIGNAL_FILE):
                os.remove(SIGNAL_FILE)
                print("\n[Signal received]")
                break
            try:
                _ = await page.title()
            except Exception:
                print("\n[Browser window closed]")
                break

        # ── Dump results ──────────────────────────────────────────
        print(f"\nToken: {'YES' if captured['token'] else 'NO'}")
        print(f"Endpoints: {len(captured['endpoints'])}")
        print(f"JSON responses: {len(captured['responses'])}")
        for ep in sorted(captured["endpoints"]):
            print(f"  {ep}")

        for r in captured["responses"]:
            if set(r["keys"]) & {"data", "content", "items", "videos", "folders", "batchContent"}:
                captured["folder_api_url"] = r["path"]
                print(f"\n[!] Folder-listing API: {r['path']}")

        out = {
            "course_id": course_id,
            "token": captured["token"],
            "endpoints": sorted(captured["endpoints"]),
            "folder_api_candidate": captured["folder_api_url"],
            "responses": captured["responses"],
        }
        with open(OUTPUT, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nSaved: {OUTPUT}")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
