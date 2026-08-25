"""High-definition screens via the v0 Platform API.

v0 is headless: post a prompt, get back a running preview URL. That URL is then
photographed by a screenshot provider and the PNG goes straight into the
proposal. No canvas, no export, no upload, no human in the loop.

Needs two keys:
    V0_API_KEY          from vercel.com/account/tokens
    SCREENSHOT_PROVIDER  screenshotone | urlbox | browserless | none
    plus that provider's key
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request

V0_KEY = os.environ.get("V0_API_KEY", "")
V0_BASE = os.environ.get("V0_API_BASE", "https://api.v0.dev/v1")
V0_MODEL = os.environ.get("V0_MODEL", "v0-1.5-md")
POLL_SECONDS = float(os.environ.get("V0_POLL_SECONDS", "2"))
POLL_LIMIT = int(os.environ.get("V0_POLL_LIMIT", "20"))

SHOT_PROVIDER = os.environ.get("SCREENSHOT_PROVIDER", "none").lower()
SHOT_KEY = os.environ.get("SCREENSHOT_API_KEY", "")

VIEWPORT = {"phone": (390, 844), "tablet": (1024, 768), "web": (1440, 900)}


def configured():
    return bool(V0_KEY) and SHOT_PROVIDER != "none" and bool(SHOT_KEY)


def _post(url, payload, headers, timeout=90):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers=dict({"content-type": "application/json"}, **headers))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(url, headers, timeout=60):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _v0_headers():
    return {"authorization": "Bearer %s" % V0_KEY}


def create_chat(prompt):
    """Start a v0 chat and return (chat_id, preview_url or None)."""
    out = _post("%s/chats" % V0_BASE,
                {"message": prompt, "modelConfiguration": {"modelId": V0_MODEL}},
                _v0_headers())
    return out.get("id"), _preview_of(out)


def _preview_of(chat):
    for key in ("demo", "demoUrl", "previewUrl"):
        if chat.get(key):
            return chat[key]
    latest = chat.get("latestVersion") or {}
    for key in ("demoUrl", "demo", "previewUrl"):
        if latest.get(key):
            return latest[key]
    return None


def wait_for_preview(chat_id):
    """v0 builds asynchronously, so poll until the sandbox is serving."""
    for _ in range(POLL_LIMIT):
        chat = _get("%s/chats/%s" % (V0_BASE, chat_id), _v0_headers())
        url = _preview_of(chat)
        if url:
            return url
        time.sleep(POLL_SECONDS)
    raise RuntimeError("v0 did not return a preview URL in time for chat %s"
                       % chat_id)


# ------------------------------------------------------------- screenshotting
def screenshot(url, device="phone"):
    w, h = VIEWPORT.get(device, VIEWPORT["phone"])
    if SHOT_PROVIDER == "screenshotone":
        q = urllib.parse.urlencode({
            "access_key": SHOT_KEY, "url": url, "viewport_width": w,
            "viewport_height": h, "device_scale_factor": 2, "format": "png",
            "full_page": "false", "block_cookie_banners": "true",
            "delay": 3, "response_type": "by_format"})
        req = urllib.request.Request("https://api.screenshotone.com/take?%s" % q)
    elif SHOT_PROVIDER == "urlbox":
        q = urllib.parse.urlencode({
            "url": url, "width": w, "height": h, "retina": "true",
            "format": "png", "delay": 3000})
        req = urllib.request.Request(
            "https://api.urlbox.com/v1/render/png?%s" % q,
            headers={"authorization": "Bearer %s" % SHOT_KEY})
    elif SHOT_PROVIDER == "browserless":
        payload = {"url": url, "options": {"type": "png"},
                   "viewport": {"width": w, "height": h, "deviceScaleFactor": 2},
                   "gotoOptions": {"waitUntil": "networkidle2"}}
        req = urllib.request.Request(
            "https://production-sfo.browserless.io/screenshot?token=%s" % SHOT_KEY,
            data=json.dumps(payload).encode(), method="POST",
            headers={"content-type": "application/json"})
    else:
        raise RuntimeError("SCREENSHOT_PROVIDER is not configured")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def build_screen(prompt, device="phone"):
    """prompt -> PNG bytes. One screen, start to finish."""
    chat_id, url = create_chat(prompt)
    if not url:
        url = wait_for_preview(chat_id)
    return screenshot(url, device), url


BRAND = ("Light UI, generous white space, rounded 12px cards, soft shadows, a "
         "geometric sans typeface, primary accent blue #2563EB, deep navy header "
         "#3A5498, success green #68AC5A, neutral text #11141A on #F6F8FB "
         "backgrounds. Use real photographic imagery from Unsplash source URLs "
         "for every image slot, never grey placeholder blocks.")


def prompt_for(slot, project_name):
    device = slot.get("device", "phone")
    frame = {"phone": "a single mobile app screen at 390x844",
             "tablet": "a single landscape tablet app screen at 1024x768",
             "web": "a single desktop web dashboard screen at 1440x900"}[device]
    points = "\n".join("- %s" % p for p in slot.get("points", []) if p)
    return (
        "Build %s for \"%s\", named \"%s\".\n\n%s\n\n"
        "The screen must show exactly this content:\n%s\n\n"
        "Render it as one static page with no routing, no scrolling beyond the "
        "viewport, and no explanatory text outside the interface itself. "
        "Fill the whole viewport." % (frame, project_name, slot.get("title", ""),
                                      BRAND, points))


# ------------------------------------------------------------- key self-test
def test_keys():
    """Actually call both services and report what happened, per key."""
    out = {"v0": {"set": bool(V0_KEY)}, "screenshot": {
        "provider": SHOT_PROVIDER, "set": bool(SHOT_KEY)}}

    if not V0_KEY:
        out["v0"]["ok"] = False
        out["v0"]["detail"] = "V0_API_KEY is not set."
    else:
        try:
            _get("%s/user" % V0_BASE, _v0_headers(), timeout=20)
            out["v0"]["ok"] = True
            out["v0"]["detail"] = "Key accepted."
        except Exception as exc:                              # noqa: BLE001
            code = getattr(exc, "code", None)
            out["v0"]["ok"] = False
            out["v0"]["detail"] = (
                "v0 rejected the key (HTTP 401). Check V0_API_KEY."
                if code == 401 else
                "v0 could not be reached: %s" % exc)

    if SHOT_PROVIDER == "none" or not SHOT_KEY:
        out["screenshot"]["ok"] = False
        out["screenshot"]["detail"] = ("Set SCREENSHOT_PROVIDER and "
                                       "SCREENSHOT_API_KEY.")
    else:
        try:
            png = screenshot("https://example.com", "phone")
            ok = png[:8] == b"\x89PNG\r\n\x1a\n"
            out["screenshot"]["ok"] = ok
            out["screenshot"]["bytes"] = len(png)
            out["screenshot"]["detail"] = (
                "Key accepted, %d KB test image returned." % (len(png)//1024)
                if ok else "Reply was not a PNG, so the key is probably wrong.")
        except Exception as exc:                              # noqa: BLE001
            code = getattr(exc, "code", None)
            out["screenshot"]["ok"] = False
            if code in (401, 403):
                out["screenshot"]["detail"] = (
                    "Provider rejected the key (HTTP %s). For ScreenshotOne use "
                    "the ACCESS key, not the secret key." % code)
            elif code == 429:
                out["screenshot"]["detail"] = "Key works but you are out of quota."
            else:
                out["screenshot"]["detail"] = "Could not reach provider: %s" % exc
    out["ready"] = bool(out["v0"].get("ok") and out["screenshot"].get("ok"))
    return out
