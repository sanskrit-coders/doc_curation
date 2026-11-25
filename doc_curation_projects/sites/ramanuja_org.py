import logging
import os
import time
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from curation_utils import file_helper
from doc_curation.md.file import MdFile

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)

BASE_URL = "https://www.ramanuja.org/sri/BhaktiListArchives/Article"
HOME_URL = "https://www.ramanuja.org/sri/BhaktiListArchives/HomePage?from=Web.BhaktiListArchives"
DEST_BASE = "/home/vvasuki/gitland/hindu-comm/mail_stream/rAmAnuja_org"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def get_soup(url, retries=5, delay=5):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            logging.warning("HTTP %s for %s (attempt %d/%d)", r.status_code, url, attempt, retries)
        except Exception as e:
            logging.warning("Error fetching %s (attempt %d/%d): %s", url, attempt, retries, e)
        time.sleep(delay * attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def parse_home():
    """Return list of (stream, month_param) from the home page."""
    soup = get_soup(HOME_URL)
    entries = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "Article?p=" not in href:
            continue
        full = urljoin("https://www.ramanuja.org/sri/BhaktiListArchives/", href)
        p = parse_qs(urlparse(full).query).get("p", [None])[0]
        if not p or not p.endswith("/index.html"):
            continue
        if p.startswith("poetry/"):
            stream = "poetry"
        elif p.startswith("rituals/"):
            stream = "rituals"
        else:
            stream = "bhakti-list"
        key = (stream, p)
        if key in seen:
            continue
        seen.add(key)
        entries.append((stream, p))
    logging.info("Found %d month indexes from home page", len(entries))
    return entries


def _p_from_href(href):
    full = urljoin("https://www.ramanuja.org/sri/BhaktiListArchives/", href)
    return parse_qs(urlparse(full).query).get("p", [None])[0]


def parse_month_index(p_param):
    """Return list of threads, each a list of article dicts in thread order.

    Each article dict: {p, title}. Threading is inferred from <li> nesting.
    Only links within the same month dir are included.
    """
    url = f"{BASE_URL}?p={p_param}"
    soup = get_soup(url)
    month_dir = p_param.replace("/index.html", "")
    month_dir_unquoted = unquote(month_dir)

    def in_month(p):
        if not p or p.endswith("/index.html") or p.endswith("/"):
            return False
        pu = unquote(p)
        return pu.startswith(month_dir_unquoted + "/")

    # Collect article links in document order, with their li depth
    items = []  # (depth, p, title)
    seen = set()
    for a in soup.select("a[href*='Article?p=']"):
        href = a.get("href", "")
        p = _p_from_href(href)
        if not in_month(p) or p in seen:
            continue
        # Skip date/subject/author index pages
        base = os.path.basename(unquote(p))
        if base in ("date.html", "subject.html", "author.html", "attachment.html"):
            continue
        seen.add(p)
        li = a.find_parent("li")
        depth = 0
        cur = li.parent if li else None
        while cur:
            if cur.name == "li":
                depth += 1
            cur = cur.parent
        title = a.get_text(" ", strip=True)
        items.append((depth, p, title))

    # Group into threads: depth 0 starts a new thread
    threads = []
    current = []
    for depth, p, title in items:
        if depth == 0 or not current:
            if current:
                threads.append(current)
            current = [{"p": p, "title": title}]
        else:
            current.append({"p": p, "title": title})
    if current:
        threads.append(current)
    logging.info("Month %s: %d threads, %d articles", p_param, len(threads), len(items))
    return threads


def scrape_article(p_param):
    """Return dict with title, author, date, body, url."""
    url = f"{BASE_URL}?p={p_param}"
    soup = get_soup(url)
    title_el = soup.select_one("h1")
    title = title_el.get_text(" ", strip=True) if title_el else "UNKNOWN"
    author = None
    for a in soup.select("a[href*='google.com/search']"):
        txt = a.get_text(" ", strip=True)
        if txt and "ramanuja.org" not in txt.lower():
            author = txt
            break
    atime = soup.select_one("#atime, .atime")
    date_str = atime.get_text(" ", strip=True).lstrip("•").strip() if atime else None
    msg_div = soup.select_one("div.bhakti-list-message")
    if msg_div:
        pre = msg_div.select_one("pre")
        body = pre.get_text() if pre else msg_div.get_text("\n")
    else:
        pre = soup.select_one("pre")
        body = pre.get_text() if pre else ""
    return {"title": title, "author": author, "date_str": date_str, "body": body.strip("\n"), "url": url}


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return dateparser.parse(date_str, fuzzy=True)
    except Exception:
        return None


def thread_dir_path(stream, first_dt, thread_title, thread_id):
    subject_slug = file_helper.get_storage_name(thread_title or "unknown", source_script=None)
    thread_subdir = "%s__%s" % (subject_slug, thread_id[:8])
    if first_dt is not None:
        return os.path.join(DEST_BASE, stream, str(first_dt.year), "%02d" % first_dt.month, "%02d" % first_dt.day, thread_subdir)
    return os.path.join(DEST_BASE, stream, "undated", thread_subdir)


def dump_thread(stream, thread_articles):
    """Dump a thread (list of {p,title}) into google-groups-like layout."""
    # Fetch root first to determine thread dir; skip if already complete.
    try:
        root = scrape_article(thread_articles[0]["p"])
    except Exception as e:
        logging.error("Failed to fetch root %s: %s", thread_articles[0]["p"], e)
        return 0
    root["index_title"] = thread_articles[0]["title"]
    root["dt"] = parse_date(root.get("date_str"))
    thread_title = root["title"] or root["index_title"] or "UNKNOWN"
    root_p = unquote(thread_articles[0]["p"])
    thread_id = os.path.splitext(os.path.basename(root_p))[0]
    # We need first_dt; may be in root or later messages. Use root for now, refine if needed.
    first_dt = root["dt"]
    tdir = thread_dir_path(stream, first_dt, thread_title, thread_id)
    if os.path.isdir(tdir):
        existing = [f for f in os.listdir(tdir) if f.endswith(".md")]
        if len(existing) >= len(thread_articles):
            logging.info("Thread complete, skipping: %s", tdir)
            return len(existing)
    # Fetch remaining messages
    messages = [root]
    for art in thread_articles[1:]:
        time.sleep(0.3)
        try:
            data = scrape_article(art["p"])
        except Exception as e:
            logging.error("Failed to fetch %s: %s", art["p"], e)
            continue
        data["index_title"] = art["title"]
        data["dt"] = parse_date(data.get("date_str"))
        messages.append(data)
    # Refine first_dt and tdir if root had no date
    if first_dt is None:
        first_dt = next((m["dt"] for m in messages if m["dt"] is not None), None)
        tdir = thread_dir_path(stream, first_dt, thread_title, thread_id)
    for index, msg in enumerate(messages):
        author = msg["author"] or "UNKNOWN_AUTHOR"
        date_str = msg["date_str"] or "UNKNOWN_DATE"
        title = "%03d %s" % (index, author)
        fname = file_helper.get_storage_name(title, source_script=None) + ".md"
        fpath = os.path.join(tdir, fname)
        if os.path.exists(fpath):
            continue
        content = f"[[{author}\t{date_str} [Source]({msg['url']})]]\n\n{msg['body']}\n"
        md_file = MdFile(file_path=fpath)
        md_file.dump_to_file(content=content, metadata={"title": title}, dry_run=False)
    return len(messages)


def archive_bhakti_list(streams=None):
    entries = parse_home()
    if streams is not None:
        entries = [e for e in entries if e[0] in set(streams)]
    total = 0
    for stream, p_param in entries:
        logging.info("=== Stream %s month %s ===", stream, p_param)
        try:
            threads = parse_month_index(p_param)
        except Exception as e:
            logging.error("Failed to parse month index %s: %s", p_param, e)
            continue
        for thread in threads:
            try:
                total += dump_thread(stream, thread)
            except Exception as e:
                logging.error("Failed thread %s: %s", thread[0].get("p") if thread else "?", e)
        time.sleep(1)
    logging.info("Done. Processed %d messages.", total)
    return total


if __name__ == "__main__":
    archive_bhakti_list()
