/**
 * classplus-grab — paste into browser console on classplusapp.com
 * Captures JWT token + encrypted contentId for use with classplus-dl.sh
 *
 * Usage:
 *   1. Open classplusapp.com, log in
 *   2. Open DevTools → Console (F12)
 *   3. Paste this entire script, press Enter
 *   4. Click any video to play it
 *   5. Both values appear in console — copy them
 *
 * Run cpGrab.help() for usage info.
 */

(function () {
  "use strict";

  // ── JWT extraction: try multiple sources ──────────────────────────
  function findToken() {
    // Try localStorage variants
    for (const key of ["token", "accessToken", "x-access-token", "jwt", "auth"]) {
      const v = localStorage.getItem(key);
      if (v && v.startsWith("eyJ")) return v;
    }
    // Try sessionStorage
    for (const key of ["token", "accessToken", "x-access-token", "jwt", "auth"]) {
      const v = sessionStorage.getItem(key);
      if (v && v.startsWith("eyJ")) return v;
    }
    // Try cookies
    for (const c of document.cookie.split("; ")) {
      const [k, v] = c.split("=");
      if (v && v.startsWith("eyJ")) return v;
    }
    // Try IndexedDB / Redux store (best effort)
    try {
      const rootEl = document.getElementById("root");
      if (rootEl && rootEl._reactRootContainer) {
        // walk React fiber tree for token
        function walkFiber(fiber, depth) {
          if (!fiber || depth > 15) return null;
          if (
            fiber.memoizedState?.current?.token ||
            fiber.memoizedState?.token
          ) {
            return fiber.memoizedState.token || fiber.memoizedState.current.token;
          }
          const next = fiber.memoizedState?.next || fiber.memoizedState?.current;
          return walkFiber(fiber.child, depth + 1) || walkFiber(fiber.sibling, depth + 1);
        }
        // React 18+ uses __reactFiber$
        const fiberKey = Object.keys(rootEl).find((k) => k.startsWith("__reactFiber"));
        if (fiberKey) {
          const token = walkFiber(rootEl[fiberKey], 0);
          if (token) return token;
        }
      }
    } catch (_) { /* not critical */ }
    return null;
  }

  // ── Intercept fetch for jw-signed-url calls ──────────────────────
  const origFetch = window.fetch;
  let capturedEncId = null;

  window.fetch = function (...args) {
    const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "";
    if (url.includes("jw-signed-url")) {
      const u = new URL(url, window.location.origin);
      capturedEncId = u.searchParams.get("contentId");
      window.__CP_ENC_ID = capturedEncId;
      console.log(
        "%c◆ CLASSPLUS GRAB %c│ Encrypted contentId captured:",
        "color:#0f0;font-weight:bold",
        "color:inherit",
        capturedEncId
      );
      console.log(
        "%c◆ CLASSPLUS GRAB %c│ Copy: %c" + capturedEncId,
        "color:#0f0;font-weight:bold",
        "color:inherit",
        "color:#ff0"
      );
    }
    // Also capture token from request headers
    const req = args[1] || {};
    if (req.headers) {
      const h = new Headers(req.headers);
      const tok = h.get("x-access-token");
      if (tok) {
        window.__CP_TOKEN = tok;
      }
    }
    return origFetch.apply(this, args);
  };

  // ── Expose helpers ────────────────────────────────────────────────
  const token = findToken();
  if (token) window.__CP_TOKEN = token;

  window.cpGrab = {
    token: () => window.__CP_TOKEN || findToken() || "(not found — check Network tab)",
    encId: () => window.__CP_ENC_ID || "(not captured — click a video first)",
    all: () => ({
      token: window.cpGrab.token(),
      encId: window.cpGrab.encId(),
    }),
    help: () => {
      console.log(
        "%c╔══════════════════════════════════════════╗\n" +
          "%c║   classplus-grab — Video Download Helper  ║\n" +
          "%c╠══════════════════════════════════════════╣\n" +
          "%c║                                            ║\n" +
          "%c║ 1. Click any video to play it              ║\n" +
          "%c║ 2. Run: cpGrab.all()                       ║\n" +
          "%c║ 3. Copy both values                        ║\n" +
          "%c║ 4. Run: classplus-dl.sh <encId>            ║\n" +
          "%c║    (set CLASS PLUS_TOKEN env var)           ║\n" +
          "%c║                                            ║\n" +
          "%c║ Commands:                                  ║\n" +
          "%c║  cpGrab.token()  — show JWT token          ║\n" +
          "%c║  cpGrab.encId()  — show encrypted contentId ║\n" +
          "%c║  cpGrab.all()    — show both               ║\n" +
          "%c║  cpGrab.help()   — show this               ║\n" +
          "%c╚══════════════════════════════════════════╝",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0",
        "color:#0f0"
      );
    },
  };

  // ── Report ────────────────────────────────────────────────────────
  const found = token ? "✓ found" : "✗ not found in storage (will capture from API calls)";
  console.log(
    "%c◆ CLASSPLUS GRAB %c│ JWT: %c" + found,
    "color:#0f0;font-weight:bold",
    "color:inherit",
    token ? "color:#0f0" : "color:#fa0"
  );
  if (token) {
    console.log(
      "%c◆ CLASSPLUS GRAB %c│ Token: %c" +
        token.substring(0, 40) +
        "...",
      "color:#0f0;font-weight:bold",
      "color:inherit",
      "color:#888"
    );
  }
  console.log(
    "%c◆ CLASSPLUS GRAB %c│ Ready. Click a video to capture contentId.",
    "color:#0f0;font-weight:bold",
    "color:inherit"
  );
  console.log(
    "%c◆ CLASSPLUS GRAB %c│ Then run %ccpGrab.all()%c to see both values.",
    "color:#0f0;font-weight:bold",
    "color:inherit",
    "color:#ff0",
    "color:inherit"
  );
})();
