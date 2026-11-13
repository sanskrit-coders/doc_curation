"""Smoke-test Meta AI browser automation: list conversations, start one, prompt.

Run:
    ~/gitland/python_venv/bin/python doc_curation/llm/meta/broswer_ui.py

Env:
    META_HEADED=1   show the browser window (debugging)
    *https_proxy    used automatically when set (sandboxed/proxied networks)

Reusable entry point (lazy: the shared client and browser are created on the
first call and reused afterwards):

    from broswer_ui import get_response, close_ai
    print(get_response("What is 2+2?"))
    print(get_response("Describe this image.", files=["/tmp/pic.png"]))
    print(get_response("Generate an image of a cat.", include_files=True))
    close_ai()

This script runtime-patches metaai_api's PlaywrightBackend (installed in
site-packages, so it is patched here rather than edited) to fix three bugs
that made prompt() hang for the full timeout and return an empty message:

1. Text was read with `[class*="assistant-message"]` + last match, but the
   last match is the empty `group/assistant-message-actions` action bar, so
   the text was always "" and the wait loop never finished early. Fixed by
   reading `[data-testid="assistant-message"]` scoped to `.markdown-content`.
2. Math answers render as `<img alt="...">` (LaTeX) with zero textContent,
   so even a correct node yields "". Fixed with an img-alt fallback.
3. Completion was guessed by text stability instead of the page's own
   `data-streaming-complete="true"` flag. The wait now keys off that flag.
4. Overlay dismissal clicked "Connect", which OPENS the Settings/Apps modal
   and covers the composer, so typing/clicking silently failed and nothing
   was ever submitted. The dismiss pass now only closes real dialogs (X /
   Escape) and never clicks Connect/Accept/OK.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from metaai_api import MetaAI
from metaai_api.exceptions import ConnectionError, MetaAIError
from metaai_api.playwright_backend import PlaywrightBackend
from metaai_api.utils import is_media_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("metaai_api").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Read the exact assistant message node (attached, so innerText keeps layout).
# The thinking header ("Show thinking" / "Locating objects in image" / ...) is
# hidden via visibility while reading: innerText skips unrendered nodes, so it
# is excluded without disturbing layout, wherever it sits in the render (it is
# sometimes inside .markdown-content, sometimes a sibling). Fall back to
# textContent + img alt text for LaTeX-image-only answers.
EXTRACT_JS = """() => {
  const msgs = document.querySelectorAll('[data-testid="assistant-message"]');
  if (msgs.length === 0) return {text: '', done: false, state: 'none', count: 0};
  const last = msgs[msgs.length - 1];
  const state = last.getAttribute('data-streaming-state') || '';
  const done = last.getAttribute('data-streaming-complete') === 'true';
  const hidden = [];
  last.querySelectorAll('[data-testid="thinking-status"], [data-testid="subagent-cot-list"]').forEach(n => {
    hidden.push([n, n.style.visibility]);
    n.style.visibility = 'hidden';
  });
  let text = '';
  try {
    text = (last.innerText || '').trim();
  } finally {
    hidden.forEach(([n, v]) => { n.style.visibility = v; });
  }
  if (!text) {
    const alts = [];
    last.querySelectorAll('.markdown-content img[alt], img.ur-sm-latex-image').forEach(img => {
      const a = (img.alt || '').trim();
      if (a) alts.push(a);
    });
    if (alts.length) text = alts.join(' ').trim();
  }
  return {text, done, state, count: msgs.length};
}"""

# Composer attachment state: inline image nodes (alt = filename) and document
# tiles (text = filename + type badge). Both render once the upload lands.
ATTACH_STATE_JS = """() => {
  const images = Array.from(
    document.querySelectorAll('[data-inline-image-id] img[alt]')
  ).map(i => (i.alt || '').trim()).filter(Boolean);
  const tiles = Array.from(
    document.querySelectorAll('[class*="attachment-tile"]')
  ).map(t => (t.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
  return {images, tiles};
}"""

# Response media is collected from assistant messages only, so the user's own
# attached files (rendered in the user bubble) never count as generated media.
# LaTeX render images are skipped: they illustrate the text (already captured
# via img alt) rather than being response files.
MEDIA_STATE_JS = """() => {
  const out = [];
  document.querySelectorAll('[data-testid="assistant-message"]').forEach(m => {
    m.querySelectorAll('img[src]').forEach(i => {
      if (i.matches('.ur-sm-latex-image, [data-latex]')) return;
      out.push({url: i.src, kind: 'image'});
    });
    m.querySelectorAll('video[src]').forEach(v => out.push({url: v.src, kind: 'video'}));
    m.querySelectorAll('video source[src], picture source[src]').forEach(s =>
      out.push({url: s.src, kind: 'video'}));
    m.querySelectorAll('a[href]').forEach(a => out.push({url: a.href, kind: 'file'}));
  });
  return out;
}"""


def _collect_media(page: Any) -> List[Dict[str, str]]:
    """Assistant-message media as [{url, kind}], filtered to genuine fbcdn
    files (kind: image/video/file). Never raises."""
    try:
        items = page.evaluate(MEDIA_STATE_JS) or []
    except Exception:
        return []
    out = []
    for item in items:
        url = (item.get("url") or "").strip()
        if url and "fbcdn" in url and is_media_url(url):
            out.append({"url": url, "kind": item.get("kind") or "file"})
    return out

# Visible contenteditable composer first; the hidden pre-hydration textarea
# (matched by the library's first selectors) is tried last.
INPUT_SELECTORS = [
    'div[data-testid="composer-input"][role="textbox"]',
    '[role="textbox"]',
    'div[data-testid="composer-input"] [contenteditable]',
    '[contenteditable="true"]',
    'textarea[data-testid="composer-input"]',
    'textarea[placeholder*="Ask Meta"]',
    'textarea',
]


def _proxy_server() -> Optional[str]:
    for var in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        proxy = (os.environ.get(var) or "").strip()
        if proxy:
            return proxy
    return None


def _setup_with_proxy(self) -> None:
    """Original setup() plus proxy support for sandboxed/proxied networks."""
    from playwright.sync_api import sync_playwright

    self._check_installed()
    self._playwright = sync_playwright().start()
    launch_kwargs: Dict[str, Any] = {
        "headless": not self.headed,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }
    proxy = _proxy_server()
    if proxy:
        launch_kwargs["proxy"] = {"server": proxy}
        logger.info("Using proxy from environment for browser launch")
    self._browser = self._playwright.chromium.launch(**launch_kwargs)

    context = self._browser.new_context(
        user_agent=self.user_agent,
        viewport={"width": 1280, "height": 720},
    )
    context.add_cookies(
        [{"name": k, "value": v, "domain": ".meta.ai", "path": "/"}
         for k, v in self.cookies.items()]
    )
    self._page = context.new_page()
    self._page.goto("https://www.meta.ai/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    self._dismiss_overlays()
    self._page.reload(wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    self._dismiss_overlays()
    self._ready = True
    logger.info("Playwright backend ready")


def _dismiss_overlays_fixed(self) -> None:
    """Close real dialogs only. Never clicks "Connect"/"Accept"/"OK": on the
    meta.ai home page "Connect" opens the Settings/Apps modal, which then
    covers the composer and silently breaks typing and submitting."""
    page = self._page
    try:
        for _ in range(3):
            try:
                dlg = page.query_selector('[role="dialog"]')
                if dlg is None or not dlg.is_visible():
                    break
            except Exception:
                break
            closed = False
            for sel in (
                '[role="dialog"] button[aria-label="Close"]',
                '[role="dialog"] button[aria-label="Dismiss"]',
                'button:has-text("Dismiss")',
                'button:has-text("Got it")',
            ):
                try:
                    btn = page.query_selector(sel)
                    if btn is not None and btn.is_visible():
                        btn.click(timeout=2000)
                        time.sleep(1)
                        closed = True
                        break
                except Exception:
                    continue
            if not closed:
                try:
                    page.keyboard.press("Escape")
                    time.sleep(1)
                except Exception:
                    break
    except Exception:
        pass


def _extract_text_fixed(self) -> str:
    try:
        result = self._page.evaluate(EXTRACT_JS) or {}
        return result.get("text", "") or ""
    except Exception:
        return ""


def _wait_for_response_fixed(
    self, timeout: int, existing_urls: Optional[Set[str]] = None
) -> Tuple[List[str], str]:
    """Wait for new media URLs or the assistant text, keyed off the page's
    own streaming-complete flag instead of text stability alone."""
    urls: Set[str] = set()
    last_text = ""
    stable = 0
    start = time.time()
    done_at: Optional[float] = None
    existing = existing_urls or set()

    while time.time() - start < timeout:
        time.sleep(2)
        for item in _collect_media(self._page):
            if item["url"] not in existing:
                urls.add(item["url"])

        try:
            result = self._page.evaluate(EXTRACT_JS) or {}
        except Exception:
            continue
        text = result.get("text", "") or ""
        done = bool(result.get("done"))
        stable = stable + 1 if text == last_text else 0
        last_text = text
        if done and done_at is None:
            done_at = time.time()

        if done and text:
            time.sleep(1)  # let late chunks (e.g. LaTeX images) land
            try:
                settled = self._page.evaluate(EXTRACT_JS) or {}
                text = settled.get("text", "") or text
            except Exception:
                pass
            return sorted(urls), text
        if urls and done and not text:
            # Media done with no text stream (image answers): return at once.
            return sorted(urls), text
        if done and not text:
            # The flag can flip before the markdown renders (vision answers);
            # give it a grace period instead of returning "" immediately.
            if done_at is not None and time.time() - done_at > 15:
                return sorted(urls), text
            continue
        if urls and stable >= 2:
            # Media arrived with no text stream (image answers).
            return sorted(urls), text

    return sorted(urls), last_text


def _attach_files_fixed(self, files: Sequence[str], timeout: int = 60) -> None:
    """Attach local files via the composer "+" button.

    Flow: focus composer (the button renders on focus) -> click "Add
    attachment" -> click the dropzone in the dialog -> answer the file
    chooser -> wait until every file shows as an inline image or a document
    tile. Raises ConnectionError when any step fails.
    """
    page = self._page
    try:
        ed = page.query_selector('div[data-testid="composer-input"][role="textbox"]')
        if ed is not None and ed.is_visible():
            ed.click(timeout=3000)
            time.sleep(1)
    except Exception:
        pass

    plus = None
    for _ in range(10):
        try:
            cand = page.query_selector('button[aria-label="Add attachment"]')
            if cand is not None and cand.is_visible():
                plus = cand
                break
        except Exception:
            pass
        time.sleep(1)
    if plus is None:
        raise ConnectionError("Add attachment button not found")
    plus.click(timeout=3000)
    time.sleep(2)

    dropzone = None
    for _ in range(10):
        try:
            cand = page.query_selector('[data-testid="composer-attachment-dropzone"]')
            if cand is not None and cand.is_visible():
                dropzone = cand
                break
        except Exception:
            pass
        time.sleep(1)
    if dropzone is None:
        raise ConnectionError("Attachment dialog did not open")
    with page.expect_file_chooser(timeout=10000) as chooser_info:
        dropzone.click(timeout=3000)
    chooser_info.value.set_files(list(files))
    logger.info("Attaching %d file(s): %s", len(files), [Path(f).name for f in files])

    wanted = {Path(f).name: Path(f).stem for f in files}
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            state = page.evaluate(ATTACH_STATE_JS) or {}
        except Exception:
            continue
        images = state.get("images", []) or []
        tiles = state.get("tiles", []) or []
        matched = sum(
            1
            for name, stem in wanted.items()
            if name in images or any(stem and stem in tile for tile in tiles)
        )
        if matched >= len(wanted) or len(images) + len(tiles) >= len(wanted):
            logger.info("All %d attachment(s) present in composer", len(files))
            return
    raise ConnectionError(
        f"Attachments did not appear in composer: {sorted(wanted)} "
        "(unsupported type or upload failed)"
    )


def _send_message_fixed(
    self,
    prompt: str,
    timeout: int = 120,
    thinking_mode: bool = False,
    files: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Original send_message() with visible-first input selectors, optional
    file attachments, and submit verification."""
    if not self._ready:
        self.setup()

    self._dismiss_overlays()
    self._switch_mode("Thinking" if thinking_mode else "Instant")
    self._dismiss_overlays()

    if files:
        self._attach_files(list(files))

    composer_text_js = """() => {
        const ed = document.querySelector(
          'div[data-testid="composer-input"][role="textbox"]');
        return ed ? (ed.innerText || '') : '';
      }"""

    def _landed() -> str:
        try:
            return self._page.evaluate(composer_text_js) or ""
        except Exception:
            return ""

    # Type first, verify the text landed, and only then press Enter (the
    # composer clears on submit, so the check must run before Enter).
    typed_how = None
    for selector in INPUT_SELECTORS:
        try:
            el = self._page.query_selector(selector)
            if el is None or not el.is_visible():
                continue
            el.scroll_into_view_if_needed(timeout=5000)
            time.sleep(0.5)
            el.click(timeout=3000)
            time.sleep(0.3)
            self._page.keyboard.type(prompt, delay=20)
            time.sleep(0.5)
            if prompt.strip()[:20] not in _landed():
                continue
            self._page.keyboard.press("Enter")
            typed_how = selector
            logger.info("Typed prompt using selector: %s", selector)
            break
        except Exception:
            continue

    if typed_how is None:
        try:
            self._page.evaluate(
                """(text) => {
                    const ed = document.querySelector(
                      'div[data-testid="composer-input"][role="textbox"]');
                    if (!ed) throw new Error('composer not found');
                    ed.focus();
                    if (!document.execCommand('insertText', false, text))
                      throw new Error('insertText failed');
                  }""",
                prompt,
            )
            time.sleep(0.5)
            if prompt.strip()[:20] not in _landed():
                raise ConnectionError("JS fallback text did not land in composer")
            self._page.keyboard.press("Enter")
            typed_how = "javascript-fallback"
            logger.info("Typed prompt using JavaScript fallback")
        except Exception as e:
            raise ConnectionError(f"Could not find chat input: {e}")

    # Verify submit navigated to a conversation; retry once via send button.
    if "/prompt/" not in self._page.url:
        submitted = False
        for _ in range(8):
            time.sleep(2)
            try:
                url = self._page.url
            except Exception:
                url = ""
            if "/prompt/" in url:
                submitted = True
                break
        if not submitted:
            try:
                send_btn = self._page.query_selector(
                    'button[aria-label*="Send"], button[type="submit"]'
                )
                if send_btn is not None and send_btn.is_visible():
                    send_btn.click(timeout=3000)
            except Exception:
                pass
            for _ in range(5):
                time.sleep(2)
                try:
                    url = self._page.url
                except Exception:
                    url = ""
                if "/prompt/" in url:
                    submitted = True
                    break
        if not submitted:
            raise ConnectionError("Prompt did not submit (stayed on home page)")

    existing_urls = {item["url"] for item in _collect_media(self._page)}

    urls, text = self._wait_for_response(timeout, existing_urls)
    # Re-read kinds for the collected urls (DOM is settled by now).
    kinds = {item["url"]: item["kind"] for item in _collect_media(self._page)}
    files = [{"url": url, "kind": kinds.get(url, "file")} for url in urls]
    return {
        "urls": urls,
        "text": text,
        "conversation_id": self._get_conversation_id(),
        "files": files,
    }


def _prompt_with_files(
    self,
    message: str,
    stream: bool = False,
    attempts: int = 0,
    new_conversation: bool = True,
    timeout: int = 60,
    thinking_mode: bool = False,
    files: Optional[Sequence[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Original prompt() plus a files passthrough to the browser backend.

    Extra image/media kwargs are accepted and ignored, matching the stock
    browser path (which never forwarded them); files are the supported way
    to attach content here and require the Playwright backend.
    """
    self._get_browser()  # Ensure browser is initialized
    if new_conversation:
        self._browser.new_chat()

    send_kwargs: Dict[str, Any] = {"timeout": timeout, "thinking_mode": thinking_mode}
    if files:
        if not isinstance(self._browser, PlaywrightBackend):
            raise MetaAIError("file attachments require the Playwright backend")
        send_kwargs["files"] = list(files)
    result = self._browser.send_message(message, **send_kwargs)
    return {
        "message": result.get("text", ""),
        "conversation_id": result.get("conversation_id"),
        "raw": result,
    }


# Apply the runtime patches before MetaAI creates its backend.
PlaywrightBackend._dismiss_overlays = _dismiss_overlays_fixed
PlaywrightBackend.setup = _setup_with_proxy
PlaywrightBackend._extract_text = _extract_text_fixed
PlaywrightBackend._wait_for_response = _wait_for_response_fixed
PlaywrightBackend._attach_files = _attach_files_fixed
PlaywrightBackend.send_message = _send_message_fixed
MetaAI.prompt = _prompt_with_files


_ai: Optional[MetaAI] = None


def get_ai() -> MetaAI:
    """Return the shared MetaAI client, creating it on first use.

    The browser backend itself starts lazily inside MetaAI on the first
    call that needs it (prompt/list/new), so importing this module never
    launches a browser.
    """
    global _ai
    if _ai is None:
        cookies_path = Path(
            os.environ.get("META_COOKIES_PATH", "").strip()
            or (Path(__file__).parent / "cookies_local.json")
        )
        cookies = json.loads(cookies_path.read_text())
        headed = os.environ.get("META_HEADED", "").strip() == "1"
        _ai = MetaAI(cookies=cookies, headed=headed)
    return _ai


def close_ai() -> None:
    """Close the shared client and drop it so the next get_ai() rebuilds it."""
    global _ai
    if _ai is not None:
        try:
            _ai.close()
        finally:
            _ai = None


def _normalize_files(
    files: Optional[Union[str, Path, Sequence[Union[str, Path]]]],
) -> Optional[List[str]]:
    """Validate attachments up front and return absolute path strings.

    Raises FileNotFoundError before any browser work starts.
    """
    if files is None:
        return None
    if isinstance(files, (str, Path)):
        files = [files]
    paths = []
    for f in files:
        p = Path(f).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"attachment not found: {f}")
        paths.append(str(p))
    return paths or None


def get_response(
    prompt: str,
    timeout: int = 120,
    thinking_mode: bool = False,
    files: Optional[Union[str, Path, Sequence[Union[str, Path]]]] = None,
    include_files: bool = False,
) -> Union[str, Dict[str, Any]]:
    """Send prompt in a fresh conversation, wait for the answer, return it.

    Readying is lazy: the shared MetaAI client (and its browser) is created
    on the first call and reused by later calls. Pass thinking_mode=True for
    longer reasoning (slower); default Instant mode answers in seconds.

    files optionally attaches local files (a path or list of paths): images,
    PDFs, office docs, video, and plain/code text are accepted. Missing files
    raise FileNotFoundError before the browser is touched.

    By default returns the answer text. With include_files=True returns
    {"message", "files", "conversation_id"}, where files lists response
    files (e.g. generated images) as {"url", "kind"} dicts with kind in
    image/video/file. The urls are short-lived signed links: download them
    promptly with a plain GET (no auth needed).
    """
    paths = _normalize_files(files)
    reply = get_ai().prompt(
        prompt,
        new_conversation=True,
        timeout=timeout,
        thinking_mode=thinking_mode,
        files=paths,
    )
    message = (reply.get("message") or "").strip()
    if not include_files:
        return message
    return {
        "message": message,
        "files": (reply.get("raw") or {}).get("files", []),
        "conversation_id": reply.get("conversation_id"),
    }


def main() -> None:
    ai = get_ai()
    try:
        convs = ai.list_conversations()
        print(f"convs: {len(convs)}")
        for conv in convs[:5]:
            print(f"  - {conv['title']} ({conv['id']})")

        ai.new_conversation()
        print("new: ok")

        answer = get_response("What is 2+2?", timeout=90)
        print(f"prompt: {answer!r}")
        if not answer:
            raise SystemExit("ERROR: empty reply (check screenshot/debug output above)")
    finally:
        close_ai()


if __name__ == "__main__":
    main()
