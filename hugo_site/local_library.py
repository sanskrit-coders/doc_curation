import json
import logging
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from hugo_site import md_to_site_path, VISHVASA_DIR
from hugo_site import appscript_client

# ── Paths ──────────────────────────────────────────────────────────────────────
GS_DIR        = "/media/vvasuki/vData/text/granthasangrahaH"
PDF_LIB_DIR   = os.path.expanduser(
    "~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib")
CACHE_FILE    = os.path.join(PDF_LIB_DIR, ".archive_cache.json")
DEFAULT_LLM_LABEL = "LLM-crouton"

# Uploaders whose items we match against
UPLOADERS = ["kashcidv@gmail.com", "vishvas.vasuki@gmail.com"]

# Archive.org uploader search URL template
IA_SEARCH_URL = (
    "https://archive.org/advancedsearch.php"
    "?q=uploader%3A%22{uploader}%22"
    "&fl[]=identifier,title,mediatype,publicdate"
    "&rows=2000&output=json"
)

# Exempt directories (don't rename, don't map these)
EXEMPT_PREFIXES = [
    "bhAShA/",
    "vedAH/shAkalam/rangan/",
    "kalpaH/kANe/",
    "kAvyam/shrIvaiShNavakRtam/drAviDam/divya-kaviH/4000-divya-prabandham/",
]

SKIP_DIRS = {".git", "node_modules", "themes", "build_github", ".system_generated", ".vscode", ".idea", "meta"}

STOP_WORDS = {
    "the", "a", "an", "of", "in", "is", "to", "and", "or", "for", "that", "this", "with",
    "are", "be", "as", "at", "by", "from", "has", "it", "its", "not", "on", "was", "which",
    "will", "i", "he", "she", "we", "they", "you", "but", "so", "if", "do", "did", "can",
    "all", "have", "had", "been", "his", "her", "their", "our", "than", "then", "when",
    "what", "who", "how", "one", "two", "three", "may", "also", "only", "there", "these",
    "those", "page", "volume", "translation", "commentary", "edition", "brahman", "vishnu",
    "shiva", "india", "sanskrit",
}

GENERIC_TERMS = {
    "kalpah", "vedah", "kavyam", "itihasah", "puranam", "agamah", "bhasha", "mimamsa",
    "jyotisha", "koshah", "stotram", "samhita", "brahmanam", "aranyakam", "upanishat",
    "sutram", "grhyam", "shrautam", "dharmah", "smrtih", "nyayah", "vyakaranam",
    "darshanam", "mantrah", "tantram", "readme", "license", "index", "mulam", "meta",
    "content", "static", "node", "modules", "kannada", "sanskrit", "hindi", "telugu",
    "tamil", "english", "bengali", "marathi", "text", "pdf", "docx", "epub",
}

ARCHIVE_RE = re.compile(
    r"https?://(?:[a-zA-Z0-9_\-\.]+\.)?archive\.org/[^\s\)\]\>\"\'`\,]+",
    re.IGNORECASE,
)
PDF_MENTION_RE = re.compile(r"([a-zA-Z0-9_\-\.]+\.pdf)", re.IGNORECASE)
FM_TITLE_RE    = re.compile(r'^\s*title\s*[:=]\s*["\']?([^"\'\\n\\r]+)["\']?', re.MULTILINE | re.IGNORECASE)

CORRESPONDENCES = [
    # AgamaH/vaiShNavaH/shrIvaiShNavaH/ ↔ rAmAnujIyam/content/tattvam
    ("AgamaH/vaiShNavaH/shrIvaiShNavaH/",
        ["rAmAnujIyam/content/tattvam"]),
    # kalpaH/vaiShNavaH/shrIvaiShNavaH/ ↔ rAmAnujIyam/content/kriyA
    ("kalpaH/vaiShNavaH/shrIvaiShNavaH/",
        ["rAmAnujIyam/content/kriyA"]),
    # kAvyam/shrIvaiShNavakRtam/ ↔ multiple vishvAsa kAvyam locations
    ("kAvyam/shrIvaiShNavakRtam/",
        ["rAmAnujIyam/content/kAvyam",
         "purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam",
         "rAmAyaNam/content/kAvyam",
         "mahAbhAratam/content/kAvyam"]),
]


# ── Basic Helpers ──────────────────────────────────────────────────────────────

def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_exempt(rel_path, exempt_prefixes=EXEMPT_PREFIXES):
    return any(rel_path.startswith(p) for p in exempt_prefixes)


def read_first_chunk(path, chars=1500, skip=150):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(chars + skip)
        return content[skip : skip + chars]
    except Exception:
        return ""


def get_rare_words(text, min_len=5, max_words=50):
    words = re.findall(r"[a-zA-Z]{5,}", text.lower())
    words = [w for w in words if w not in STOP_WORDS]
    return sorted(set(words), key=lambda w: -len(w))[:max_words]


# ── Spreadsheet Access ─────────────────────────────────────────────────────────

def get_sheet_entries(script_url=None):
    """Retrieve all entries from the Google Sheet via Apps Script.

    Returns:
        dict: {
            "ok": bool,
            "header": list[str],
            "rows": list[dict], # {source_path, archive_urls, site_path, map_source, Pending, __row}
            "entries_by_source_path": dict[str, dict]
        }
    """
    sheet = appscript_client.get_sheet(script_url)
    if not sheet.get("ok"):
        raise RuntimeError(f"Failed to fetch spreadsheet entries: {sheet.get('error')}")
    rows = sheet.get("rows", [])
    entries_by_source_path = {r["source_path"]: r for r in rows if "source_path" in r}
    sheet["entries_by_source_path"] = entries_by_source_path
    return sheet


# ── Stage 1: Scan local PDFs ───────────────────────────────────────────────────

def scan_local_pdfs(gs_dir=GS_DIR, skip_dirs=SKIP_DIRS, exempt_prefixes=EXEMPT_PREFIXES):
    logging.info(f"Scanning {gs_dir} for PDFs …")
    t0 = time.time()
    pdfs = []
    size_to_paths = defaultdict(list)

    for root, dirs, files in os.walk(gs_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            if not fname.lower().endswith(".pdf"):
                continue
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, gs_dir)
            if is_exempt(rel, exempt_prefixes=exempt_prefixes):
                continue
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            stem = fname[:-4]
            parts = stem.split("_", 1)
            title = parts[1] if len(parts) > 1 else parts[0]
            rec = {
                "rel": rel,
                "full": full,
                "filename": fname,
                "stem": stem,
                "norm_stem": normalize(stem),
                "norm_title": normalize(title),
                "size": sz,
            }
            pdfs.append(rec)
            size_to_paths[sz].append(rel)

    logging.info(f"Found {len(pdfs)} PDFs in {time.time()-t0:.1f}s")
    return pdfs, size_to_paths


# ── Stage 2: Archive.org matching ─────────────────────────────────────────────

def load_cache(cache_file=CACHE_FILE):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache, cache_file=CACHE_FILE):
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def fetch_archive_items(cache, uploaders=UPLOADERS, cache_file=CACHE_FILE):
    logging.info("Fetching archive.org item list …")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 granthasangrahaH-map-builder"

    items = []
    for uploader in uploaders:
        try:
            url = IA_SEARCH_URL.format(uploader=requests.utils.quote(uploader, safe="@"))
            resp = session.get(url, timeout=30)
            docs = resp.json()["response"]["docs"]
            for doc in docs:
                if not any(it["identifier"] == doc["identifier"] for it in items):
                    items.append(doc)
            logging.info(f"{len(docs)} items for {uploader}")
        except Exception as e:
            logging.warning(f"Could not query {uploader}: {e}")

    to_fetch = [it for it in items if it["identifier"] not in cache]
    logging.info(f"Items to fetch metadata for: {len(to_fetch)} (cached: {len(cache)})")

    def fetch_one(doc):
        ident = doc["identifier"]
        url = f"https://archive.org/metadata/{ident}"
        for attempt in range(4):
            try:
                r = session.get(url, timeout=25)
                if r.status_code == 200:
                    return ident, r.json(), None
                return ident, None, f"HTTP {r.status_code}"
            except Exception as ex:
                if attempt == 3:
                    return ident, None, str(ex)
                time.sleep(1 + attempt)
        return ident, None, "max retries"

    if to_fetch:
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(fetch_one, doc): doc for doc in to_fetch}
            done = 0
            for fut in as_completed(futures):
                ident, meta, err = fut.result()
                done += 1
                if meta:
                    cache[ident] = meta
                if done % 50 == 0:
                    logging.info(f"… fetched {done}/{len(to_fetch)} in {time.time()-t0:.0f}s")
        save_cache(cache, cache_file=cache_file)
        logging.info(f"Saved {len(cache)} items to cache.")

    return items, cache


def match_by_size(items, cache, size_to_paths):
    logging.info("Matching archive PDFs to local PDFs by file size …")
    result = {}

    for item_doc in items:
        ident = item_doc["identifier"]
        meta  = cache.get(ident, {})
        files = meta.get("files", [])
        item_url = f"https://archive.org/details/{ident}"

        for f in files:
            fname  = f.get("name", "")
            source = f.get("source", "original")
            if source != "original":
                continue
            if not fname.lower().endswith(".pdf"):
                continue
            size_str = f.get("size")
            if not size_str or not size_str.isdigit():
                continue
            sz = int(size_str)
            if sz not in size_to_paths:
                continue

            candidates = size_to_paths[sz]
            if len(candidates) == 1:
                local_rel = candidates[0]
            else:
                base = os.path.basename(fname).lower()
                local_rel = next(
                    (c for c in candidates if os.path.basename(c).lower() == base),
                    candidates[0],
                )
            if local_rel not in result:
                result[local_rel] = {"archive_urls": [], "md_paths": [], "match_sources": []}
            if item_url not in result[local_rel]["archive_urls"]:
                result[local_rel]["archive_urls"].append(item_url)
                result[local_rel]["match_sources"].append(f"size:{fname}")

    logging.info(f"Matched {len(result)} PDFs via file size")
    return result


# ── Stage 3: vishvAsa MD scan ──────────────────────────────────────────────────

def scan_vishvasa(pdfs, existing_map, vishvasa_dir=VISHVASA_DIR, skip_dirs=SKIP_DIRS):
    logging.info(f"Scanning {vishvasa_dir} for archive.org links and PDF matches …")
    if not os.path.isdir(vishvasa_dir):
        logging.warning("vishvAsa directory not found, skipping.")
        return existing_map

    by_norm_stem  = {}
    by_norm_title = {}
    by_filename   = {}
    for p in pdfs:
        ns = p["norm_stem"]
        if len(ns) >= 4 and ns not in GENERIC_TERMS:
            by_norm_stem.setdefault(ns, []).append(p["rel"])
        nt = p["norm_title"]
        if len(nt) >= 5 and nt != ns and nt not in GENERIC_TERMS:
            by_norm_title.setdefault(nt, []).append(p["rel"])
        by_filename.setdefault(p["filename"].lower(), []).append(p["rel"])

    t0 = time.time()
    scanned = 0
    matches = 0

    for root, dirs, files in os.walk(vishvasa_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath  = os.path.join(root, fname)
            rel_md = os.path.relpath(fpath, vishvasa_dir)

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    top = "".join(fp.readline() for _ in range(40))
            except Exception:
                continue

            arch_urls   = list(dict.fromkeys(ARCHIVE_RE.findall(top)))
            pdf_mentions = list(dict.fromkeys(PDF_MENTION_RE.findall(top)))
            fm_title_m  = FM_TITLE_RE.search(top)
            title       = fm_title_m.group(1).strip().lstrip("+").strip() if fm_title_m else ""

            matched_pdfs = {}

            # Match by direct PDF filename mention
            for pm in pdf_mentions:
                base = os.path.basename(pm).lower()
                for rel in by_filename.get(base, []):
                    matched_pdfs.setdefault(rel, []).append(f"pdf_mention:{pm}")

            # Match by md filename stem
            stem = fname[:-3]
            ns = normalize(stem)
            if len(ns) >= 4 and ns not in GENERIC_TERMS:
                for rel in by_norm_stem.get(ns, []):
                    matched_pdfs.setdefault(rel, []).append(f"stem:{stem}")

            # Match by frontmatter title (try optitrans transliteration)
            if title:
                try:
                    from indic_transliteration import sanscript
                    for script in (sanscript.DEVANAGARI, sanscript.KANNADA, sanscript.TELUGU):
                        opti = sanscript.transliterate(title, script, sanscript.OPTITRANS)
                        nt = normalize(opti)
                        if len(nt) >= 6 and nt not in GENERIC_TERMS:
                            for rel in by_norm_stem.get(nt, []) + by_norm_title.get(nt, []):
                                matched_pdfs.setdefault(rel, []).append(f"title:{title}")
                            break
                except Exception:
                    pass

            if not matched_pdfs and not arch_urls:
                continue

            for rel, reasons in matched_pdfs.items():
                reason_str = " ".join(reasons)
                if not ("pdf_mention" in reason_str or "stem:" in reason_str or
                        ("title:" in reason_str and arch_urls)):
                    continue
                if rel not in existing_map:
                    existing_map[rel] = {"archive_urls": [], "md_paths": [], "match_sources": []}
                entry = existing_map[rel]
                if rel_md not in entry["md_paths"]:
                    entry["md_paths"].append(rel_md)
                    entry["match_sources"].append(f"md:{reasons[0]}")
                    matches += 1
                for au in arch_urls:
                    au_clean = re.sub(r"/page/.*", "", au)
                    if au_clean not in entry["archive_urls"]:
                        entry["archive_urls"].append(au_clean)

    logging.info(f"Scanned {scanned} MDs, added {matches} PDF→MD links in {time.time()-t0:.1f}s")
    return existing_map


# ── Stage 4: OCR text fragment matching ───────────────────────────────────────

def ocr_match(pdfs, existing_map, vishvasa_dir=VISHVASA_DIR, skip_dirs=SKIP_DIRS):
    logging.info("OCR text fragment matching for unmatched PDFs with .pdf.txt …")
    no_md = [(p["rel"], p["full"] + ".txt") for p in pdfs
             if not existing_map.get(p["rel"], {}).get("md_paths")
             and os.path.exists(p["full"] + ".txt")]
    logging.info(f"PDFs with .pdf.txt but no MD match: {len(no_md)}")
    if not no_md:
        return existing_map

    mds_with_arch = []
    for root, dirs, files in os.walk(vishvasa_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath  = os.path.join(root, fname)
            rel_md = os.path.relpath(fpath, vishvasa_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    top = "".join(fp.readline() for _ in range(20))
            except Exception:
                continue
            arch_urls = ARCHIVE_RE.findall(top)
            if arch_urls:
                mds_with_arch.append((rel_md, fpath, arch_urls))

    logging.info(f"Building inverted index from {len(mds_with_arch)} MDs with archive URLs …")
    t0 = time.time()
    inverted   = {}
    md_registry = []

    for rel_md, md_path, arch_urls in mds_with_arch:
        text = read_first_chunk(md_path, chars=1500, skip=100)
        if len(text) < 100:
            continue
        words = get_rare_words(text)
        idx = len(md_registry)
        md_registry.append((rel_md, arch_urls))
        for w in words:
            inverted.setdefault(w, []).append(idx)

    logging.info(f"Index: {len(inverted)} words, {len(md_registry)} MDs in {time.time()-t0:.1f}s")
    t0 = time.time()
    new_matches = 0

    for rel, txt_path in no_md:
        text = read_first_chunk(txt_path, chars=1500, skip=150)
        if len(text) < 100:
            continue
        words = get_rare_words(text)
        if len(words) < 5:
            continue
        votes = {}
        for w in words:
            if w in inverted:
                rarity = 1.0 / max(1, len(inverted[w]))
                for idx in inverted[w]:
                    votes[idx] = votes.get(idx, 0) + rarity
        if not votes:
            continue
        best_idx   = max(votes, key=lambda x: votes[x])
        best_score = votes[best_idx]
        if best_score < 1.5:
            continue
        rel_md, arch_urls = md_registry[best_idx]
        if rel not in existing_map:
            existing_map[rel] = {"archive_urls": [], "md_paths": [], "match_sources": []}
        entry = existing_map[rel]
        if rel_md not in entry["md_paths"]:
            entry["md_paths"].append(rel_md)
            entry["match_sources"].append(f"ocr:{best_score:.2f}")
            new_matches += 1
        for au in arch_urls:
            au_clean = re.sub(r"/page/.*", "", au)
            if au_clean not in entry["archive_urls"]:
                entry["archive_urls"].append(au_clean)

    logging.info(f"OCR stage added {new_matches} links in {time.time()-t0:.1f}s")
    return existing_map


# ── Stage 5: Correspondence-guided matching ────────────────────────────────────

def _corr_index(vis_subdirs, vishvasa_dir=VISHVASA_DIR, skip_dirs=SKIP_DIRS):
    inverted = {}
    registry = []
    for sub in vis_subdirs:
        subpath = os.path.join(vishvasa_dir, sub)
        if not os.path.isdir(subpath):
            continue
        for root, dirs, files in os.walk(subpath):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                rel_md = os.path.relpath(fpath, vishvasa_dir)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        top = "".join(fp.readline() for _ in range(40))
                except Exception:
                    continue
                arch_urls = re.findall(
                    r"https?://(?:[a-zA-Z0-9_\-\.]+\.)?archive\.org/[^\s\)\]\>\"\'`\,]+",
                    top, re.I)
                stem = fname[:-3]
                words = set(re.findall(r"[a-zA-Z]{4,}", stem.lower()))
                for d in rel_md.split(os.sep)[:-1]:
                    words.update(re.findall(r"[a-zA-Z]{4,}", d.lower()))
                stop = {"the","a","an","of","in","is","to","and","or","for","that","this",
                        "with","are","be","as","at","by","from","has","it","its","not","on",
                        "was","which","will","i","he","she","we","they","you","but","so",
                        "if","do","did","can","all","have","had","been","his","her","their",
                        "our","than","then","when","what","who","how","one","two","three",
                        "may","also","only","there","these","those","page","volume","sri",
                        "shri","swami","vol","content","tattvam","kriya","kavyam"}
                generic = {"kalpah","vedah","kavyam","itihasah","puranam","agamah","bhasha",
                           "mimamsa","jyotisha","koshah","stotram","samhita","brahmanam",
                           "aranyakam","upanishat","sutram","grhyam","shrautam","dharmah",
                           "smrtih","nyayah","vyakaranam","darshanam","mantrah","tantram",
                           "readme","license","index","mulam","meta","content","static",
                           "node","modules","hindi","telugu","tamil","english","bengali",
                           "marathi","text","pdf","docx","epub","sarvaprast"}
                words -= stop
                words = {w for w in words if w not in generic}
                idx = len(registry)
                registry.append((rel_md, arch_urls))
                for w in words:
                    inverted.setdefault(w, []).append(idx)
    return inverted, registry


def correspondence_match(pdfs, result_map, correspondences=CORRESPONDENCES,
                         vishvasa_dir=VISHVASA_DIR, skip_dirs=SKIP_DIRS):
    logging.info("Applying directory correspondences …")
    new_links = 0
    pdf_by_rel = {p["rel"]: p for p in pdfs}

    for gs_prefix, vis_subdirs in correspondences:
        candidates = [(rel, pdf_by_rel[rel]) for rel in pdf_by_rel
                      if rel.startswith(gs_prefix)
                      and not result_map.get(rel, {}).get("md_paths")]
        if not candidates:
            continue
        inv, reg = _corr_index(vis_subdirs, vishvasa_dir=vishvasa_dir, skip_dirs=skip_dirs)

        for rel, pinfo in candidates:
            rel_parts = rel.split("/")
            stem = rel_parts[-1][:-4]
            q_words = set(re.findall(r"[a-zA-Z]{4,}", stem.lower()))
            for part in rel_parts[:-1]:
                q_words.update(re.findall(r"[a-zA-Z]{4,}", part.lower()))
            txt_path = pinfo["full"] + ".txt"
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8", errors="ignore") as fp:
                        chunk = fp.read(1500)[150:]
                    ocr_w = set(re.findall(r"[a-zA-Z]{5,}", chunk.lower()))
                    q_words.update(list(ocr_w)[:30])
                except Exception:
                    pass

            if len(q_words) < 2:
                continue
            votes = {}
            for w in q_words:
                if w in inv:
                    rarity = 1.0 / max(1, len(inv[w]))
                    for idx in inv[w]:
                        votes[idx] = votes.get(idx, 0) + rarity
            if not votes:
                continue
            best_idx   = max(votes, key=lambda x: votes[x])
            best_score = votes[best_idx]
            if best_score < 0.8:
                continue
            rel_md, arch_urls = reg[best_idx]
            if rel not in result_map:
                result_map[rel] = {"archive_urls": [], "md_paths": [], "match_sources": []}
            result_map[rel].setdefault("match_sources", [])
            if rel_md not in result_map[rel]["md_paths"]:
                result_map[rel]["md_paths"].append(rel_md)
                result_map[rel]["match_sources"].append(f"correspondence:{best_score:.2f}")
                new_links += 1
            for au in arch_urls:
                au_c = re.sub(r"/page/.*", "", au)
                if au_c not in result_map[rel]["archive_urls"]:
                    result_map[rel]["archive_urls"].append(au_c)

    logging.info(f"Directory correspondences added {new_links} new PDF→MD links")
    return result_map


# ── Identifying New PDFs & Mapping to Site Pages ───────────────────────────────

def find_new_pdf_mappings(sheet_entries=None, script_url=None, gs_dir=GS_DIR,
                          vishvasa_dir=VISHVASA_DIR, llm_label=DEFAULT_LLM_LABEL,
                          cache_file=CACHE_FILE):
    """Identify local PDFs not yet in the spreadsheet and map them to site pages / archive URLs.

    Args:
        sheet_entries (dict, optional): Result from get_sheet_entries(). If omitted, fetched automatically.
        script_url (str, optional): Apps Script /exec URL.
        gs_dir (str, optional): Directory of granthasangrahaH library.
        vishvasa_dir (str, optional): Directory of vishvAsa repository.
        llm_label (str, optional): Fallback provenance label when matching is non-algorithmic.
        cache_file (str, optional): Cache file path for archive.org metadata.

    Returns:
        list[dict]: List of row dicts for new PDFs with keys:
                    'source_path', 'archive_urls', 'site_path', 'map_source'.
    """
    if sheet_entries is None:
        sheet_entries = get_sheet_entries(script_url=script_url)

    known_source_paths = set(sheet_entries.get("entries_by_source_path", {}).keys())

    # 1. Scan local PDFs
    pdfs, size_to_paths = scan_local_pdfs(gs_dir=gs_dir)

    # 2. Archive items matching
    cache = load_cache(cache_file=cache_file)
    items, cache = fetch_archive_items(cache, cache_file=cache_file)
    result_map = match_by_size(items, cache, size_to_paths)

    # 3. Scan vishvasa MDs
    result_map = scan_vishvasa(pdfs, result_map, vishvasa_dir=vishvasa_dir)

    # 4. OCR text match
    result_map = ocr_match(pdfs, result_map, vishvasa_dir=vishvasa_dir)

    # 5. Directory correspondence match
    result_map = correspondence_match(pdfs, result_map, vishvasa_dir=vishvasa_dir)

    # 6. Filter only PDFs that are not already in the spreadsheet
    new_rows = []
    for p in sorted(pdfs, key=lambda x: x["rel"]):
        rel = p["rel"]
        if rel in known_source_paths:
            continue
        info = result_map.get(rel, {})
        arch = list(dict.fromkeys(info.get("archive_urls", [])))
        mds = list(dict.fromkeys(info.get("md_paths", [])))
        site_paths = [md_to_site_path(m) for m in mds]
        sources = list(dict.fromkeys(info.get("match_sources", [])))
        map_source = ";".join(sources) if sources else llm_label

        new_rows.append({
            "source_path": rel,
            "archive_urls": "\n".join(arch),
            "site_path": "\n".join(site_paths),
            "map_source": map_source,
        })

    logging.info(f"Found {len(new_rows)} local PDFs missing from the spreadsheet")
    return new_rows


def sync_new_pdfs_to_sheet(script_url=None, dry_run=False, llm_label=DEFAULT_LLM_LABEL,
                           gs_dir=GS_DIR, vishvasa_dir=VISHVASA_DIR):
    """Find local PDFs missing from sheet, map them to site pages, and append to sheet."""
    sheet_entries = get_sheet_entries(script_url=script_url)
    new_mappings = find_new_pdf_mappings(
        sheet_entries=sheet_entries,
        script_url=script_url,
        gs_dir=gs_dir,
        vishvasa_dir=vishvasa_dir,
        llm_label=llm_label,
    )

    if not new_mappings:
        logging.info("No new PDFs to sync to sheet.")
        return 0

    if dry_run:
        logging.info(f"[dry-run] Would append {len(new_mappings)} new PDFs to sheet.")
        return len(new_mappings)

    resp = appscript_client.post_append_rows(script_url, new_mappings)
    if not resp.get("ok"):
        raise RuntimeError(f"appendRows failed: {resp}")
    logging.info(f"Successfully appended {resp.get('added', len(new_mappings))} rows to sheet.")
    return resp.get("added", len(new_mappings))
