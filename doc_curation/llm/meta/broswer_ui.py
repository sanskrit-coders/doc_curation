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
from typing import Any, Dict, List, Optional, Set, Tuple

from metaai_api import MetaAI
from metaai_api.exceptions import ConnectionError
from metaai_api.playwright_backend import PlaywrightBackend
from metaai_api.utils import is_media_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("metaai_api").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Read the exact assistant message node (attached, so innerText keeps layout),
# scoped to the markdown body to exclude the "Show thinking" header. Fall back
# to textContent + img alt text for LaTeX-image-only answers.
EXTRACT_JS = """() => {
  const msgs = document.querySelectorAll('[data-testid="assistant-message"]');
  if (msgs.length === 0) return {text: '', done: false, state: 'none', count: 0};
  const last = msgs[msgs.length - 1];
  const state = last.getAttribute('data-streaming-state') || '';
  const done = last.getAttribute('data-streaming-complete') === 'true';
  const scope = last.querySelector('.markdown-content') || last;
  let text = (scope.innerText || '').trim();
  if (!text) {
    const alts = [];
    scope.querySelectorAll('img[alt]').forEach(img => {
      const a = (img.alt || '').trim();
      if (a) alts.push(a);
    });
    const tc = (scope.textContent || '').replace(/\\s+/g, ' ').trim();
    text = [tc, ...alts].filter(Boolean).join(' ').trim();
  }
  return {text, done, state, count: msgs.length};
}"""

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
    existing = existing_urls or set()

    while time.time() - start < timeout:
        time.sleep(2)
        try:
            elements = self._page.query_selector_all('img[src], video[src], source[src], a[href]')
            for el in elements:
                src = el.get_attribute("src") or el.get_attribute("href") or ""
                if src and "fbcdn" in src and is_media_url(src) and src not in existing:
                    urls.add(src)
        except Exception:
            pass

        try:
            result = self._page.evaluate(EXTRACT_JS) or {}
        except Exception:
            continue
        text = result.get("text", "") or ""
        done = bool(result.get("done"))
        stable = stable + 1 if text == last_text else 0
        last_text = text

        if urls and done:
            return sorted(urls), text
        if done and text:
            time.sleep(1)  # let late chunks (e.g. LaTeX images) land
            try:
                settled = self._page.evaluate(EXTRACT_JS) or {}
                text = settled.get("text", "") or text
            except Exception:
                pass
            return sorted(urls), text
        if done and stable >= 2:
            return sorted(urls), text
        if urls and stable >= 2:
            # Media arrived with no text stream (image answers).
            return sorted(urls), text

    return sorted(urls), last_text


def _send_message_fixed(
    self, prompt: str, timeout: int = 120, thinking_mode: bool = False
) -> Dict[str, Any]:
    """Original send_message() with visible-first input selectors."""
    if not self._ready:
        self.setup()

    self._dismiss_overlays()
    self._switch_mode("Thinking" if thinking_mode else "Instant")
    self._dismiss_overlays()

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

    existing_urls: Set[str] = set()
    try:
        elements = self._page.query_selector_all('img[src], video[src], source[src], a[href]')
        for el in elements:
            src = el.get_attribute("src") or el.get_attribute("href") or ""
            if src and "fbcdn" in src:
                existing_urls.add(src)
    except Exception:
        pass

    urls, text = self._wait_for_response(timeout, existing_urls)
    return {"urls": urls, "text": text, "conversation_id": self._get_conversation_id()}


# Apply the runtime patches before MetaAI creates its backend.
PlaywrightBackend._dismiss_overlays = _dismiss_overlays_fixed
PlaywrightBackend.setup = _setup_with_proxy
PlaywrightBackend._extract_text = _extract_text_fixed
PlaywrightBackend._wait_for_response = _wait_for_response_fixed
PlaywrightBackend.send_message = _send_message_fixed


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


def get_response(prompt: str, timeout: int = 120, thinking_mode: bool = False) -> str:
    """Send prompt in a fresh conversation, wait for the answer, return its text.

    Readying is lazy: the shared MetaAI client (and its browser) is created
    on the first call and reused by later calls. Pass thinking_mode=True for
    longer reasoning (slower); default Instant mode answers in seconds.
    """
    reply = get_ai().prompt(
        prompt, new_conversation=True, timeout=timeout, thinking_mode=thinking_mode
    )
    return (reply.get("message") or "").strip()


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
