#!/usr/bin/env python3
"""
update_map.py — Regenerate map.csv for the granthasangrahaH library.

Canonical location (tooling):
    ~/gitland/sanskrit-coders/doc_curation/vishvaasa_sites/update_map.py

Data location (unchanged):
    ~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib/map.csv

Usage:
    ~/gitland/python_venv/bin/python \\
        ~/gitland/sanskrit-coders/doc_curation/vishvaasa_sites/update_map.py [--llm-label LLM-crouton]

What this script does:
  1. Scans all PDFs in granthasangrahaH/ and builds a local index (size, stem, title).
  2. Queries archive.org for items uploaded by kashcidv@gmail.com / vishvas.vasuki@gmail.com
     and matches archive-item PDFs to local PDFs by exact file size.
  3. Scans ~/gitland/vishvAsa .md files for archive.org URLs and PDF mentions,
     and matches them to local PDFs by stem/title/archive-URL linkage.
  4. Uses an inverted-word-index over OCR text (.pdf.txt sidecars) to match
     remaining unmatched PDFs to vishvAsa .md files.
  5. Uses directory-correspondence hints (CORRESPONDENCES) to match PDFs in known
     subject subtrees to their counterpart vishvAsa directories.
  6. Writes pdf-lib/map.csv mapping source_path (relative PDF path) to archive_urls
     and site_path (Hugo site URL), with map_source recording how each mapping was
     found. Algorithmic rows use real sources (size:/md:/ocr:/correspondence:);
     rows with no algorithmic source fall back to the LLM label (--llm-label,
     default "LLM-crouton"; historical rows use "LLM-claude", etc.). Manually
     curated rows (ut-dharma:* and map_source == "manual") are preserved across
     regenerations.

Outputs (in the pdf-lib data directory, not next to this script):
    map.csv              — the main mapping file (source_path, archive_urls, site_path, map_source)
    .archive_cache.json  — cached archive.org metadata (auto-generated)

Apps Script callers (push/check helpers for the Google Sheet mirror) live
alongside this script in the same vishvaasa_sites/ directory:
    appscript_client.py     — GET/POST helpers (edit-suggestion + appendRows)
    push_map_to_sheet.py    — push map.csv rows to the sheet (chained edit or append)
    check_sheet.py          — GET the sheet and report header/row counts

Dependencies (all in ~/gitland/python_venv):
    requests, indic_transliteration
"""

import os
import re
import csv
import json
import time
import argparse
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ──────────────────────────────────────────────────────────────────────
# This tool lives in doc_curation/vishvaasa_sites/, but map.csv itself stays in
# the Hugo pdf-lib directory. Keep those two locations distinct.
GS_DIR        = "/media/vvasuki/vData/text/granthasangrahaH"
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))   # doc_curation/vishvaasa_sites/
PDF_LIB_DIR   = os.path.expanduser(
    "~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib")
VISHVASA_DIR  = os.path.expanduser("~/gitland/vishvAsa")
OUTPUT_CSV    = os.path.join(PDF_LIB_DIR, "map.csv")
SITE_BASE     = "https://vishvasa.github.io/"
CACHE_FILE    = os.path.join(PDF_LIB_DIR, ".archive_cache.json")  # cached archive metadata
# Back-compat alias (older code / external callers used META_DIR for the data dir).
META_DIR      = PDF_LIB_DIR

# ── LLM provenance ─────────────────────────────────────────────────────────────
# Rows whose mapping was produced or curated by an LLM are stamped with the
# backend label, e.g. "LLM-crouton", "LLM-claude", etc. Algorithmic rows keep
# their real match_sources (size:/md:/ocr:/correspondence:). Override with
# --llm-label (e.g. --llm-label LLM-claude for historical re-runs).
DEFAULT_LLM_LABEL = "LLM-crouton"
LLM_LABEL         = DEFAULT_LLM_LABEL

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_exempt(rel_path):
    return any(rel_path.startswith(p) for p in EXEMPT_PREFIXES)


def md_to_site_path(md_path):
    """Convert a vishvAsa MD path (relative to ~/gitland/vishvAsa/) to a Hugo site URL.

    Example:
        AgamaH_vaiShNavaH/content/vaikhAnasaH/AgamaH/atri-saMhitA/samUrtArchanAdhikaraNam.md
        -> https://vishvasa.github.io/AgamaH_vaiShNavaH/vaikhAnasaH/AgamaH/atri-saMhitA/samUrtArchanAdhikaraNam/
    _index.md / index.md -> directory URL.
    """
    md_path = (md_path or "").strip()
    if not md_path:
        return ""
    if "/content/" in md_path:
        prefix, rest = md_path.split("/content/", 1)
        md_path = prefix + "/" + rest
    else:
        md_path = md_path.lstrip("/")
    if md_path.endswith("/_index.md"):
        md_path = md_path[: -len("/_index.md")] + "/"
    elif md_path.endswith("/index.md"):
        md_path = md_path[: -len("/index.md")] + "/"
    elif md_path.endswith(".md"):
        md_path = md_path[: -len(".md")] + "/"
    elif not md_path.endswith("/"):
        md_path = md_path + "/"
    return SITE_BASE + md_path


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


# ── Stage 1: Scan local PDFs ───────────────────────────────────────────────────

def scan_local_pdfs():
    print(f"[1] Scanning {GS_DIR} for PDFs …")
    t0 = time.time()
    pdfs = []
    size_to_paths = defaultdict(list)

    for root, dirs, files in os.walk(GS_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if not fname.lower().endswith(".pdf"):
                continue
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, GS_DIR)
            if is_exempt(rel):
                continue
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            stem = fname[:-4]
            # title part = after first "_" if present
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

    print(f"    Found {len(pdfs)} PDFs in {time.time()-t0:.1f}s")
    return pdfs, size_to_paths


# ── Stage 2: Archive.org matching ─────────────────────────────────────────────

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def fetch_archive_items(cache):
    print("[2] Fetching archive.org item list …")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 granthasangrahaH-map-builder"

    items = []
    for uploader in UPLOADERS:
        try:
            url = IA_SEARCH_URL.format(uploader=requests.utils.quote(uploader, safe="@"))
            resp = session.get(url, timeout=30)
            docs = resp.json()["response"]["docs"]
            for doc in docs:
                if not any(it["identifier"] == doc["identifier"] for it in items):
                    items.append(doc)
            print(f"    {len(docs)} items for {uploader}")
        except Exception as e:
            print(f"    Warning: could not query {uploader}: {e}")

    to_fetch = [it for it in items if it["identifier"] not in cache]
    print(f"    Items to fetch metadata for: {len(to_fetch)} (cached: {len(cache)})")

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
                    print(f"    … fetched {done}/{len(to_fetch)} in {time.time()-t0:.0f}s")
        save_cache(cache)
        print(f"    Saved {len(cache)} items to cache.")

    return items, cache


def match_by_size(items, cache, size_to_paths):
    print("[2b] Matching archive PDFs to local PDFs by file size …")
    result = {}  # rel_path -> {"archive_urls": [], "md_paths": [], "match_sources": []}

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

    print(f"    Matched {len(result)} PDFs via file size")
    return result


# ── Stage 3: vishvAsa MD scan ──────────────────────────────────────────────────

def scan_vishvasa(pdfs, existing_map):
    print(f"[3] Scanning {VISHVASA_DIR} for archive.org links and PDF matches …")
    if not os.path.isdir(VISHVASA_DIR):
        print("    vishvAsa directory not found, skipping.")
        return existing_map

    # Build lookup structures
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

    for root, dirs, files in os.walk(VISHVASA_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath  = os.path.join(root, fname)
            rel_md = os.path.relpath(fpath, VISHVASA_DIR)

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

            # Only add high-confidence matches
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

    print(f"    Scanned {scanned} MDs, added {matches} PDF→MD links in {time.time()-t0:.1f}s")
    return existing_map


# ── Stage 4: OCR text fragment matching ───────────────────────────────────────

def ocr_match(pdfs, existing_map):
    print("[4] OCR text fragment matching for unmatched PDFs with .pdf.txt …")
    no_md = [(p["rel"], p["full"] + ".txt") for p in pdfs
             if not existing_map.get(p["rel"], {}).get("md_paths")
             and os.path.exists(p["full"] + ".txt")]
    print(f"    PDFs with .pdf.txt but no MD match: {len(no_md)}")
    if not no_md:
        return existing_map

    # Gather MDs with archive URLs for the index
    mds_with_arch = []
    for root, dirs, files in os.walk(VISHVASA_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath  = os.path.join(root, fname)
            rel_md = os.path.relpath(fpath, VISHVASA_DIR)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    top = "".join(fp.readline() for _ in range(20))
            except Exception:
                continue
            arch_urls = ARCHIVE_RE.findall(top)
            if arch_urls:
                mds_with_arch.append((rel_md, fpath, arch_urls))

    print(f"    Building inverted index from {len(mds_with_arch)} MDs with archive URLs …")
    t0 = time.time()
    inverted   = {}  # word → list of indices
    md_registry = []  # (rel_md, arch_urls)

    for rel_md, md_path, arch_urls in mds_with_arch:
        text = read_first_chunk(md_path, chars=1500, skip=100)
        if len(text) < 100:
            continue
        words = get_rare_words(text)
        idx = len(md_registry)
        md_registry.append((rel_md, arch_urls))
        for w in words:
            inverted.setdefault(w, []).append(idx)

    print(f"    Index: {len(inverted)} words, {len(md_registry)} MDs in {time.time()-t0:.1f}s")
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

    print(f"    OCR stage added {new_matches} links in {time.time()-t0:.1f}s")
    return existing_map


# ── Directory correspondences (GS prefix → vishvAsa search dirs) ───────────────
# Add or extend entries here to guide MD matching for specific sub-collections.

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


def _corr_index(vis_subdirs):
    """Build inverted word→idx index from vishvAsa subdirs (stem + parent dirs)."""
    inverted = {}
    registry = []  # (rel_md, arch_urls)
    for sub in vis_subdirs:
        subpath = os.path.join(VISHVASA_DIR, sub)
        if not os.path.isdir(subpath):
            continue
        skip = {".git", "node_modules", "themes", "build_github",
                ".system_generated", ".vscode", ".idea", "meta"}
        for root, dirs, files in os.walk(subpath):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                rel_md = os.path.relpath(fpath, VISHVASA_DIR)
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


# ── Stage 5: Correspondence-guided matching ────────────────────────────────────

def correspondence_match(pdfs, result_map):
    """Match unmatched PDFs to MDs using directory correspondence hints."""
    print("[5] Applying directory correspondences …")
    new_links = 0
    pdf_by_rel = {p["rel"]: p for p in pdfs}

    for gs_prefix, vis_subdirs in CORRESPONDENCES:
        candidates = [(rel, pdf_by_rel[rel]) for rel in pdf_by_rel
                      if rel.startswith(gs_prefix)
                      and not result_map.get(rel, {}).get("md_paths")]
        if not candidates:
            print(f"    {gs_prefix}: no unmatched PDFs, skipping")
            continue
        print(f"    {gs_prefix}: {len(candidates)} PDFs → scanning {vis_subdirs}")
        inv, reg = _corr_index(vis_subdirs)
        print(f"      index: {len(inv)} words, {len(reg)} MDs")

        for rel, pinfo in candidates:
            rel_parts = rel.split("/")
            stem = rel_parts[-1][:-4]
            q_words = set(re.findall(r"[a-zA-Z]{4,}", stem.lower()))
            for part in rel_parts[:-1]:
                q_words.update(re.findall(r"[a-zA-Z]{4,}", part.lower()))
            # OCR sidecar boost
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

    print(f"    → {new_links} new PDF→MD links added")
    return result_map


# ── Stage 6: Write map.csv ────────────────────────────────────────────────────

def load_ut_rows():
    """Preserve manually-added rows across regens.

    Preserves:
      * UT Dharmasastra rows (ut-dharma:* in source_path or map_source)
      * Manual PDF rows with map_source == "manual" (curated PDF→site links
        that the automatic matcher cannot recover, e.g. Gautama Mitākṣarā).
    """
    try:
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    except FileNotFoundError:
        return []
    preserved = []
    for r in existing:
        src = str(r.get("source_path", ""))
        msrc = str(r.get("map_source", ""))
        if (src.startswith("ut-dharma:") or msrc.startswith("ut-dharma:")
                or msrc == "manual"):
            preserved.append(r)
    return preserved


def write_csv(result_map, ut_rows=None, llm_label=None):
    llm_label = llm_label or LLM_LABEL
    print(f"[6] Writing {OUTPUT_CSV} …")
    entries = sorted(
        [(rel, info) for rel, info in result_map.items()
         if (info.get("archive_urls") or info.get("md_paths"))
         and os.path.exists(os.path.join(GS_DIR, rel))]
    )
    ut_rows = ut_rows or []
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source_path", "archive_urls", "site_path", "map_source"])
        w.writeheader()
        for rel, info in entries:
            arch = list(dict.fromkeys(info.get("archive_urls", [])))
            mds = list(dict.fromkeys(info.get("md_paths", [])))
            site_paths = [md_to_site_path(m) for m in mds]
            sources = list(dict.fromkeys(info.get("match_sources", [])))
            # LLM provenance: algorithmic rows keep their real sources; rows
            # with no algorithmic source are stamped with the LLM label
            # (e.g. "LLM-crouton"; historical rows use "LLM-claude", etc.).
            map_source = ";".join(sources) if sources else llm_label
            w.writerow({
                "source_path": rel,
                "archive_urls": "\n".join(arch),
                "site_path": "\n".join(site_paths),
                "map_source": map_source,
            })
        for r in ut_rows:
            w.writerow({
                "source_path": r.get("source_path", ""),
                "archive_urls": r.get("archive_urls", ""),
                "site_path": r.get("site_path", ""),
                "map_source": r.get("map_source", ""),
            })
    sz = os.path.getsize(OUTPUT_CSV)
    print(f"    Wrote {len(entries)} PDF entries + {len(ut_rows)} manual/UT rows ({sz/1024:.0f} KB)")
    return {rel for rel, _ in entries}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Regenerate pdf-lib/map.csv (archive_urls + site_path per PDF).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--llm-label", default=DEFAULT_LLM_LABEL,
        help="map_source stamped on rows with no algorithmic source "
             "(LLM provenance, e.g. LLM-crouton, LLM-claude).")
    args = parser.parse_args()
    global LLM_LABEL
    LLM_LABEL = args.llm_label
    print(f"    LLM label for fallback rows: {LLM_LABEL}")

    t_start = time.time()
    ut_rows = load_ut_rows()
    if ut_rows:
        print(f"    Preserving {len(ut_rows)} existing manual/ut-dharma:* rows …")
    pdfs, size_to_paths = scan_local_pdfs()

    cache        = load_cache()
    items, cache = fetch_archive_items(cache)
    result_map   = match_by_size(items, cache, size_to_paths)

    result_map = scan_vishvasa(pdfs, result_map)
    result_map = ocr_match(pdfs, result_map)
    result_map = correspondence_match(pdfs, result_map)

    write_csv(result_map, ut_rows=ut_rows, llm_label=LLM_LABEL)
    print(f"\nDone in {time.time()-t_start:.0f}s. Outputs in {PDF_LIB_DIR}/")


if __name__ == "__main__":
    main()
