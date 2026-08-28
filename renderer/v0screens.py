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
import urllib.error
import urllib.parse
import urllib.request

V0_KEY = os.environ.get("V0_API_KEY", "")
# v1 returns a publicly reachable demoUrl. v2 previews sit behind a token and
# need a proxy, so v1 is the default for screenshotting.
V0_BASE = os.environ.get("V0_API_BASE", "https://api.v0.dev/v1")
V0_MODEL = os.environ.get("V0_MODEL", "")   # blank = v0 chooses
POLL_SECONDS = float(os.environ.get("V0_POLL_SECONDS", "2"))
POLL_LIMIT = int(os.environ.get("V0_POLL_LIMIT", "45"))
HTTP_TIMEOUT = int(os.environ.get("V0_HTTP_TIMEOUT", "300"))
RETRIES = int(os.environ.get("V0_RETRIES", "2"))

SHOT_PROVIDER = os.environ.get("SCREENSHOT_PROVIDER", "none").lower()
SHOT_KEY = os.environ.get("SCREENSHOT_API_KEY", "")

VIEWPORT = {"phone": (390, 844), "tablet": (1024, 768), "web": (1440, 900)}

# v0 serves running previews from these hosts. Anything else — v0.app,
# vercel.com — is a dashboard or a login page, never the app itself.
PUBLIC_HOSTS = ("vusercontent.net", "vercel.app", "v0.dev")
LOGIN_MARKERS = ("v0.app/chat", "vercel.com/login", "/login", "/signin",
                 "vercel.com/sso")


def is_public_preview(url):
    if not url or not url.startswith("http"):
        return False
    low = url.lower()
    if any(m in low for m in LOGIN_MARKERS):
        return False
    host = urllib.parse.urlparse(low).netloc
    return any(host == h or host.endswith("." + h) for h in PUBLIC_HOSTS)


def configured():
    return bool(V0_KEY) and SHOT_PROVIDER != "none" and bool(SHOT_KEY)


class ApiError(Exception):
    def __init__(self, status, body, url):
        self.status, self.body, self.url = status, body, url
        Exception.__init__(self, "HTTP %s from %s: %s" % (status, url, body[:300]))


def _send(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()
        except Exception:                                     # noqa: BLE001
            pass
        raise ApiError(exc.code, body, req.full_url)


def _post(url, payload, headers, timeout=None):
    return _send(urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers=dict({"content-type": "application/json"}, **headers)),
        timeout or HTTP_TIMEOUT)


def _get(url, headers, timeout=60):
    return _send(urllib.request.Request(url, headers=headers), timeout)


def _v0_headers():
    return {"authorization": "Bearer %s" % V0_KEY}


def create_chat(prompt):
    """Start a v0 chat and return (chat, public url or None)."""
    bodies = []
    if V0_MODEL:
        bodies.append({"message": prompt,
                       "modelConfiguration": {"modelId": V0_MODEL}})
    bodies.append({"message": prompt})
    bodies.append({"message": prompt, "chatPrivacy": "private"})
    last = None
    for body in bodies:
        try:
            out = _post("%s/chats" % V0_BASE, body, _v0_headers())
            chat = out.get("chat") or out.get("data") or out
            return chat, _preview_of(chat)
        except ApiError as exc:
            last = exc
            if exc.status != 422:      # only a rejected body is worth retrying
                raise
    raise last


def _preview_of(chat):
    if not isinstance(chat, dict):
        return None
    for key in ("demo", "demoUrl", "previewUrl", "url", "webUrl"):
        if chat.get(key):
            return chat[key]
    latest = chat.get("latestVersion") or {}
    for key in ("demoUrl", "demo", "previewUrl", "url"):
        if latest.get(key):
            return latest[key]
    return None


def deploy(chat):
    """Fall back to a real Vercel deployment, which is always public."""
    chat_id = chat.get("id")
    version = (chat.get("latestVersion") or {}).get("id")
    payload = {"chatId": chat_id}
    if version:
        payload["versionId"] = version
    if chat.get("projectId"):
        payload["projectId"] = chat["projectId"]
    out = _post("%s/deployments" % V0_BASE, payload, _v0_headers())
    dep = out.get("deployment") or out.get("data") or out
    for key in ("url", "webUrl", "inspectorUrl"):
        if dep.get(key):
            url = dep[key]
            return url if url.startswith("http") else "https://" + url
    raise RuntimeError("deployment created but no URL was returned: %s"
                       % json.dumps(dep)[:200])


def wait_for_preview(chat_id):
    """v0 builds asynchronously, so poll until the sandbox is serving."""
    for _ in range(POLL_LIMIT):
        out = _get("%s/chats/%s" % (V0_BASE, chat_id), _v0_headers())
        url = _preview_of(out.get("chat") or out.get("data") or out)
        if is_public_preview(url):
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
            "delay": 4, "wait_until": "networkidle0", "timeout": 60,
            "response_type": "by_format"})
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
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()[:300]
        except Exception:                                     # noqa: BLE001
            pass
        raise ApiError(exc.code, body, "screenshot(%s)" % url)


def wait_until_live(url, tries=None, gap=None):
    """A v0 sandbox spins up lazily. Poll until it answers before screenshotting."""
    tries = tries or int(os.environ.get("V0_LIVE_TRIES", "15"))
    gap = gap or float(os.environ.get("V0_LIVE_GAP", "3"))
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "user-agent": "Mozilla/5.0 (compatible; ProposalCreator/1.0)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                if r.status < 400:
                    body = r.read(4000).decode("utf-8", "ignore").lower()
                    # a shell that says "building" is not ready yet
                    if "deployment is building" not in body:
                        return True
        except Exception as exc:                              # noqa: BLE001
            last = exc
        time.sleep(gap)
    return False


def screenshot_with_retry(url, device, tries=3):
    last = None
    for i in range(tries):
        try:
            return screenshot(url, device)
        except ApiError as exc:
            last = exc
            if exc.status in (401, 403, 429):
                raise
            time.sleep(4 * (i + 1))
    raise last


def _meter(kind, units=1, stage=""):
    try:
        from .usage import record_units
        record_units(kind, "v0" if kind == "v0_build" else SHOT_PROVIDER,
                     units, stage)
    except Exception:                                         # noqa: BLE001
        pass


def build_screen(prompt, device="phone"):
    """prompt -> PNG bytes. One screen, start to finish."""
    chat, url = create_chat(prompt)
    if not url:
        try:
            url = wait_for_preview(chat.get("id"))
        except Exception:                                     # noqa: BLE001
            url = deploy(chat)
    if not wait_until_live(url):
        # the sandbox never came up; a real deployment always does
        try:
            url = deploy(chat)
            wait_until_live(url)
        except Exception as exc:                              # noqa: BLE001
            raise RuntimeError(
                "v0 built the screen but %s never started serving, and "
                "deploying it failed: %s" % (url, exc))
    return screenshot_with_retry(url, device), url


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
        last = None
        for path in ("/rate-limits", "/user", "/chats?limit=1"):
            try:
                _get("%s%s" % (V0_BASE, path), _v0_headers(), timeout=25)
                out["v0"]["ok"] = True
                out["v0"]["base"] = V0_BASE
                out["v0"]["detail"] = "Key accepted (%s%s)." % (V0_BASE, path)
                break
            except ApiError as exc:
                last = exc
                if exc.status in (401, 403):
                    break
            except Exception as exc:                          # noqa: BLE001
                last = exc
        if not out["v0"].get("ok"):
            out["v0"]["ok"] = False
            status = getattr(last, "status", None)
            body = (getattr(last, "body", "") or "")[:200]
            if status in (401, 403):
                out["v0"]["detail"] = ("v0 rejected the key (HTTP %s). Create a "
                                       "key at v0.app/chat/settings/keys. %s"
                                       % (status, body))
            else:
                out["v0"]["detail"] = ("v0 base %s returned %s. %s Try setting "
                                       "V0_API_BASE to https://api.v0.dev/v2."
                                       % (V0_BASE, status, body))

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


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

STRIP_GAP = 48          # px between screens in the generated strip


def batch_prompt(slots, project_name):
    """One page holding every screen in a row, at known sizes, so the result
    can be sliced back into individual images without guessing."""
    parts = []
    for i, slot in enumerate(slots):
        w, h = VIEWPORT.get(slot.get("device", "phone"), VIEWPORT["phone"])
        points = "\n".join("   - %s" % p for p in slot.get("points", []) if p)
        parts.append(
            'SCREEN %d — "%s", exactly %dpx wide and %dpx tall.\n%s'
            % (i + 1, slot.get("title", ""), w, h, points))
    total = sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
                for s in slots) + STRIP_GAP * (len(slots) + 1)
    tall = max(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots)
    return (
        "Build ONE static page for \"%s\" that shows %d app screens side by side "
        "in a single horizontal row.\n\n"
        "Layout rules, follow exactly:\n"
        "- The page is %dpx wide and %dpx tall, background #FFFFFF, no scrolling.\n"
        "- Use a flex row with %dpx gap and %dpx padding on every side.\n"
        "- Each screen is its own fixed-size box at the width and height given "
        "below, top-aligned, with a 1px #E7EBF2 border and 12px radius.\n"
        "- No page title, no captions, no labels, nothing outside the screens.\n\n"
        "%s\n\n%s"
        % (project_name, len(slots), total, tall + STRIP_GAP * 2,
           STRIP_GAP, STRIP_GAP, BRAND, "\n\n".join(parts)))


def slice_strip(png, slots):
    """Cut the strip back into one image per screen, at the known offsets."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    widths = [VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
              for s in slots]
    heights = [VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots]
    planned = sum(widths) + STRIP_GAP * (len(slots) + 1)
    scale = im.width / float(planned)          # the shot may be retina
    out, x = [], STRIP_GAP * scale
    for w, h in zip(widths, heights):
        box = (int(round(x)), int(round(STRIP_GAP * scale)),
               int(round(x + w * scale)), int(round((STRIP_GAP + h) * scale)))
        crop = im.crop(box)
        buf = io.BytesIO()
        crop.save(buf, format="PNG", optimize=True)
        out.append(buf.getvalue())
        x += (w + STRIP_GAP) * scale
    return out


def build_batch(slots, project_name):
    """All screens from a single v0 build. Returns a list of PNG bytes."""
    total_w = sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
                  for s in slots) + STRIP_GAP * (len(slots) + 1)
    tall = max(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots) + STRIP_GAP * 2
    last = None
    for attempt in range(RETRIES + 1):
        try:
            chat, url = create_chat(batch_prompt(slots, project_name))
            if not is_public_preview(url):
                try:
                    url = wait_for_preview(chat.get("id"))
                except Exception:                             # noqa: BLE001
                    url = None
            if not is_public_preview(url):
                url = deploy(chat)
            if not is_public_preview(url):
                raise RuntimeError("v0 returned %r, which needs a login." % url)
            png = shot_at(url, total_w, tall)
            _meter("v0_build", 1, "batch of %d" % len(slots))
            _meter("screenshot", 1, "batch strip")
            return slice_strip(png, slots), url
        except Exception as exc:                              # noqa: BLE001
            last = exc
    raise RuntimeError("v0 batch failed after %d attempts: %s" % (RETRIES + 1, last))


def shot_at(url, width, height):
    """Screenshot at an explicit viewport, for the strip."""
    if SHOT_PROVIDER == "screenshotone":
        q = urllib.parse.urlencode({
            "access_key": SHOT_KEY, "url": url, "viewport_width": min(width, 3840),
            "viewport_height": min(height, 2160), "device_scale_factor": 2,
            "format": "png", "full_page": "true", "delay": 6,
            "block_cookie_banners": "true", "response_type": "by_format"})
        req = urllib.request.Request("https://api.screenshotone.com/take?%s" % q)
    elif SHOT_PROVIDER == "urlbox":
        q = urllib.parse.urlencode({"url": url, "width": min(width, 3840),
                                    "height": min(height, 2160), "retina": "true",
                                    "format": "png", "full_page": "true",
                                    "delay": 6000})
        req = urllib.request.Request("https://api.urlbox.com/v1/render/png?%s" % q,
                                     headers={"authorization": "Bearer %s" % SHOT_KEY})
    else:
        payload = {"url": url, "options": {"type": "png", "fullPage": True},
                   "viewport": {"width": min(width, 3840),
                                "height": min(height, 2160), "deviceScaleFactor": 2},
                   "gotoOptions": {"waitUntil": "networkidle2"}}
        req = urllib.request.Request(
            "https://production-sfo.browserless.io/screenshot?token=%s" % SHOT_KEY,
            data=json.dumps(payload).encode(), method="POST",
            headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read()


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

def list_chats(limit=30):
    """Recent v0 chats, so work already paid for can be reclaimed."""
    out = _get("%s/chats?limit=%d" % (V0_BASE, limit), _v0_headers())
    rows = out.get("data") or out.get("chats") or []
    items = []
    for row in rows:
        chat = row if isinstance(row, dict) else {}
        items.append({"id": chat.get("id"),
                      "name": chat.get("name") or chat.get("title") or "",
                      "created": chat.get("createdAt") or chat.get("created_at"),
                      "url": _preview_of(chat)})
    return items


def preview_for_chat(chat_id):
    """The public URL for a chat that was already built."""
    out = _get("%s/chats/%s" % (V0_BASE, chat_id), _v0_headers())
    chat = out.get("chat") or out.get("data") or out
    url = _preview_of(chat)
    if not is_public_preview(url):
        url = deploy(chat)
    if not is_public_preview(url):
        raise RuntimeError("chat %s has no publicly reachable preview" % chat_id)
    return url


def refetch(url, device="phone"):
    """Photograph a build that already exists. No model call, no credits."""
    if not is_public_preview(url):
        raise RuntimeError("%r is not a public preview URL" % url)
    png = screenshot(url, device)
    if len(png) < 6000:
        raise RuntimeError("The screenshot of %s came back almost empty." % url)
    return png


# ---------------------------------------------------------------------------
# Asynchronous batch
# ---------------------------------------------------------------------------
# A v0 build can run for tens of minutes, which no HTTP request will survive.
# Start it, hand back the chat id, and poll until the sandbox is serving.

def start_batch(slots, project_name):
    """Kick off the build and return at once."""
    chat, url = create_chat(batch_prompt(slots, project_name))
    _meter("v0_build", 1, "batch of %d started" % len(slots))
    return {"chat_id": chat.get("id"), "url": url if is_public_preview(url) else None}


def poll_batch(chat_id, slots, deploy_if_needed=True):
    """Is it serving yet? If so, photograph and cut it up."""
    out = _get("%s/chats/%s" % (V0_BASE, chat_id), _v0_headers())
    chat = out.get("chat") or out.get("data") or out
    url = _preview_of(chat)
    if not is_public_preview(url):
        if not deploy_if_needed:
            return {"ready": False, "status": chat.get("status") or "building"}
        try:
            url = deploy(chat)
        except Exception:                                     # noqa: BLE001
            return {"ready": False, "status": "building"}
    if not is_public_preview(url):
        return {"ready": False, "status": "building"}
    total_w = sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
                  for s in slots) + STRIP_GAP * (len(slots) + 1)
    tall = max(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots) + STRIP_GAP * 2
    png = shot_at(url, total_w, tall)
    _meter("screenshot", 1, "batch strip")
    if len(png) < 6000:
        return {"ready": False, "status": "the page rendered empty, still building"}
    return {"ready": True, "url": url, "images": slice_strip(png, slots)}
