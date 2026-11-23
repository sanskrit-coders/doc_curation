#!/usr/bin/env python3
"""Keep a local copy of Pramāṇa (https://indike.org/pramana/) up to date: download a bulk dump, then apply the
changelog of each later release — only the files that changed are fetched.

    python3 pramana_sync.py init  ./pramana [--parts in.veda inf.gr …]   # the latest dump's Markdown tree
    python3 pramana_sync.py update ./pramana                             # what changed since (run it after releases)
    python3 pramana_sync.py mirror ./tree in.veda.samhita [--passages]   # any subtree straight from the API
    python3 pramana_sync.py plan in.bauddha [--depth 2]                  # sizes across the tree: plan your divisions
    python3 pramana_sync.py status ./pramana

The copy is the dump's Markdown tree: one directory per document (a path's ``.`` is ``/``; a recension ``*x`` is
``_recensions/x``, a commentary ``!x`` ``_commentaries/x``, a translation ``~x`` ``_translations/x``), each with
``metadata.json`` and, when it has text of its own, ``text.md``. The dumps and the API hold everything the site shows;
each text keeps its own licence (``licence_class``, ``open_licence`` and ``sources`` in its ``metadata.json``): texts
that are not under an open licence are for reading and study under their holders' terms. ``--open-only`` (init,
mirror) keeps only the texts under an open licence.

One file, Python 3.10+, the standard library + ``zstandard`` (``pip install zstandard``; or the ``zstd`` program).
API: https://indike.org/pramana/about/api#dumps. State is kept in ``<dir>/.pramana-sync.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get("PRAMANA_BASE", "https://indike.org/pramana")
UA = "pramana-sync/1 (+https://indike.org/pramana/about/api)"
STATE = ".pramana-sync.json"

# ---- the mapping (a copy of pramana/dumps/fstree.py; tests/test_d2_dumps.py checks they agree)
GROUP = {"*": "_recensions", "!": "_commentaries", "~": "_translations"}
PASSAGES, TEXT, META, SECTION_TEXT = "_passages", "text.md", "metadata.json", "_.md"


def doc_dir(path: str) -> str:
    out, cur = [], ""
    for ch in path:
        if ch in ".*!~":
            out.append(cur)
            if ch != ".":
                out.append(GROUP[ch])
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return "/".join(out)


def passage_path(doc_path: str, loc: str, section: bool) -> str:
    parts = ["_" + p if p.startswith("_") else p for p in loc.split(".")]
    base = (doc_dir(doc_path) + "/" + PASSAGES + "/" + "/".join(parts[:-1])).rstrip("/")
    return f"{base}/{parts[-1]}" if section else f"{base}/{parts[-1]}.md"


# ---- HTTP
def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def get(url: str, headers: dict | None = None, tries: int = 6) -> tuple[int, dict, bytes]:
    """(status, headers, body); follows redirects; retries 429/5xx with backoff (the site throttles fast clients)."""
    if url.startswith("/"):
        url = BASE + url
    for k in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, dict(e.headers), b""
            if e.code in (429, 500, 502, 503, 504) and k < tries - 1:
                wait = int(e.headers.get("Retry-After") or 0) or 2 ** (k + 1)
                time.sleep(min(wait, 120))
                continue
            raise
        except urllib.error.URLError:
            if k < tries - 1:
                time.sleep(2 ** (k + 1))
                continue
            raise
    raise RuntimeError(url)


def get_json(url: str):
    return json.loads(get(url)[2])


def q(path: str) -> str:
    return urllib.parse.quote(path, safe=".*!~@-_") if path else "%2F"


def dump_file(src: str, name: str, dest: Path | None = None) -> bytes | Path:
    """A file of the dumps: ``src`` is a local directory, a base URL, or the API's /api/v1/dumps."""
    if src and not src.startswith(("http://", "https://")):
        f = Path(src) / name
        if dest is None:
            return f.read_bytes()
        shutil.copyfile(f, dest)
        return dest
    url = (src.rstrip("/") if src else BASE + "/api/v1/dumps") + "/" + name
    if dest is None:
        return get(url)[2]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh, 1 << 20)
    tmp.replace(dest)
    return dest


def zstd_reader(f: Path):
    try:
        import zstandard
        return zstandard.ZstdDecompressor().stream_reader(open(f, "rb"))
    except ImportError:
        if not shutil.which("zstd"):
            sys.exit("needs `pip install zstandard` or the zstd program")
        return subprocess.Popen(["zstd", "-dc", str(f)], stdout=subprocess.PIPE).stdout


def sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        while b := fh.read(1 << 24):
            h.update(b)
    return h.hexdigest()


# ---- state
def load(d: Path) -> dict:
    f = d / STATE
    return json.loads(f.read_text()) if f.exists() else {}


def save(d: Path, st: dict) -> None:
    f = d / STATE
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(f)


def under(path: str, parts: list[str] | None) -> bool:
    return not parts or any(path == p or path.startswith(tuple(p + c for c in ".*!~")) for p in parts)


# ---- commands
def cmd_init(a) -> int:
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    index = json.loads(dump_file(a.dumps, "index.json"))
    rel = a.release or index["latest"]
    m = json.loads(dump_file(a.dumps, f"{rel}/manifest.json"))
    files = [f for f in m["files"] if f["form"] == a.form and (not a.parts or any(
        f["part"] == p or f["part"].startswith(p + ".") or p.startswith(f["part"] + ".") for p in a.parts))]
    total = sum(f["bytes"] for f in files)
    log(f"release {rel}: {len(files)} parts, {total / 1e6:,.1f} MB to download")
    dl = d / ".downloads"
    dl.mkdir(exist_ok=True)
    for f in files:
        local = dl / Path(f["path"]).name
        if not (local.exists() and local.stat().st_size == f["bytes"] and sha256(local) == f["sha256"]):
            log(f"  {f['path']} ({f['bytes'] / 1e6:,.1f} MB)")
            dump_file(a.dumps, f"{rel}/{f['path']}", local)
            if sha256(local) != f["sha256"]:
                sys.exit(f"sha256 of {f['path']} differs from the manifest")
        if a.form == "md":
            closed: set[str] = set()                # directories whose metadata says the text is not open
            with tarfile.open(fileobj=zstd_reader(local), mode="r|") as t:
                for mem in t:                       # a directory's metadata.json comes before its text.md
                    if not mem.isfile() or not under_tree(mem.name, a.parts):
                        continue
                    if ".." in Path(mem.name).parts or mem.name.startswith("/"):
                        continue
                    body = t.extractfile(mem).read()
                    parent, name = mem.name.rsplit("/", 1) if "/" in mem.name else ("", mem.name)
                    if a.open_only and name == META and not json.loads(body).get("open_licence"):
                        closed.add(parent)
                    if a.open_only and name == TEXT and parent in closed:
                        continue
                    out = d / mem.name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(body)
        if not a.keep:
            local.unlink()
    save(d, {"release": rel, "parts": a.parts or [], "form": a.form, "dumps": a.dumps, "base": BASE,
             "mode": "dump", "open_only": bool(a.open_only), "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    log(f"{d}: release {rel}. Later: pramana_sync.py update {d}")
    return 0


def under_tree(name: str, parts: list[str] | None) -> bool:
    if not parts:
        return True
    return any(name.startswith(doc_dir(p) + "/") for p in parts)


def write_doc(d: Path, path: str, node: dict, text: bool) -> None:
    out = d / doc_dir(path)
    out.mkdir(parents=True, exist_ok=True)
    (out / META).write_text(json.dumps(node["metadata"], ensure_ascii=False, indent=1) + "\n")
    t = out / TEXT
    if text and node.get("own_text"):
        st, _, body = get(f"/api/v1/nodes/{q(path)}/content?format=md")
        t.write_bytes(body)
    elif t.exists():
        t.unlink()


def remove_doc(d: Path, path: str) -> None:
    out = d / doc_dir(path)
    for n in (META, TEXT):
        if (out / n).exists():
            (out / n).unlink()
    while out != d and out.exists() and not any(out.iterdir()):
        out.rmdir()
        out = out.parent


def cmd_update(a) -> int:
    d = Path(a.dir)
    st = load(d)
    if not st:
        sys.exit(f"{d} has no {STATE}: run init (or mirror) first")
    since = st["release"]
    parts = st.get("parts") or None
    open_only = bool(st.get("open_only"))
    cursor, n, applied = None, 0, 0
    current = since
    while True:
        url = f"/api/v1/changes?since={q(since)}&limit=5000" + (f"&cursor={cursor}" if cursor else "")
        try:
            r = get_json(url)
        except urllib.error.HTTPError as e:
            if e.code == 410:
                sys.exit(f"release {since} is older than the changelog: run init again (a fresh dump)")
            raise
        current = r["current"]
        for c in r["changes"]:
            n += 1
            path, old = c["path"], c.get("old_path")
            if not (under(path, parts) or (old and under(old, parts))):
                continue
            keep = c.get("open_licence") or not open_only
            if c["op"] == "removed":
                remove_doc(d, path)
            elif c["op"] == "moved":
                src, dst = d / doc_dir(old), d / doc_dir(path)
                if src.exists() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.renames(src, dst)
                elif src.exists():                  # two nodes moved into one: the second's files go
                    remove_doc(d, old)
                node = get_json(f"/api/v1/nodes/{q(path)}")
                write_doc(d, path, node, keep)
            else:                                   # added | changed
                try:
                    node = get_json(f"/api/v1/nodes/{q(path)}")
                except urllib.error.HTTPError as e:
                    if e.code == 404:               # gone again in a later release: its removal follows
                        continue
                    raise
                if node.get("path") != path:
                    continue
                write_doc(d, path, node, keep)
            applied += 1
        cursor = r.get("next_cursor")
        if not cursor:
            break
    st["release"] = current
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save(d, st)
    log(f"{d}: {since} → {current}: {n} changes, {applied} applied" + (" (up to date)" if since == current else ""))
    return 0


def children(path: str, passages: bool = False):
    cursor = None
    while True:
        url = f"/api/v1/nodes/{q(path)}/children?limit=1000" + ("&passages=1" if passages else "") + \
              (f"&cursor={cursor}" if cursor else "")
        r = get_json(url)
        yield from r["children"]
        cursor = r.get("next_cursor")
        if not cursor:
            return


def cmd_mirror(a) -> int:
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    st = load(d) or {"mode": "mirror", "base": BASE, "parts": [], "etags": {}}
    etags = st.setdefault("etags", {})
    rel = get_json("/api/v1")["release"]
    todo = [a.path]
    n = 0
    while todo:
        path = todo.pop()
        node = get_json(f"/api/v1/nodes/{q(path)}")
        out = d / doc_dir(path)
        out.mkdir(parents=True, exist_ok=True)
        (out / META).write_text(json.dumps(node["metadata"], ensure_ascii=False, indent=1) + "\n")
        if node.get("own_text") and (not a.open_only or node.get("open_licence")):
            tag = etags.get(path)
            code, h, body = get(f"/api/v1/nodes/{q(path)}/content?format=md", {"If-None-Match": tag} if tag and
                                (out / TEXT).exists() else None)
            if code == 200:
                (out / TEXT).write_bytes(body)
                etags[path] = h.get("ETag") or h.get("etag")
            if a.passages:
                mirror_passages(d, path, None)
        n += 1
        if n % 100 == 0:
            log(f"  {n:,} documents")
            save(d, st)
        if node.get("children_count"):
            todo += [c["path"] for c in children(path)][::-1]
    if a.path not in st["parts"]:
        st["parts"].append(a.path)
    st["release"] = rel
    save(d, st)
    log(f"{d}: {n:,} documents of {a.path} (release {rel})")
    return 0


def mirror_passages(d: Path, doc: str, ref: str | None) -> None:
    for c in children(ref or doc, passages=ref is None):
        if c["kind"] == "section":
            (d / c["fs"]).mkdir(parents=True, exist_ok=True)
            if c.get("has_text") or c.get("title"):
                (d / c["fs"] / SECTION_TEXT).write_bytes(get(f"/api/v1/nodes/{q(c['ref'])}/content")[2])
            mirror_passages(d, doc, c["ref"])
        else:
            f = d / c["fs"]
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(get(f"/api/v1/nodes/{q(c['ref'])}/content")[2])


def cmd_plan(a) -> int:
    """Subtree sizes of a node's children, biggest first — to split a copy into repositories."""
    node = get_json(f"/api/v1/nodes/{q(a.path)}")

    def show(n, depth, ind):
        t = n.get("tree") or {}
        print(f"{ind}{n['path'] or '/':50s} {n['kind']:11s} docs {t.get('docs') or 0:>9,}  md {(t.get('md_bytes') or 0) / 1e6:>10,.1f} MB"
              f"  open {(t.get('open_md_bytes') or 0) / 1e6:>9,.1f} MB  words {t.get('words') or 0:>13,}"
              + ("" if t.get("exact") else "  (estimate)"))
        if depth > 0 and n.get("children_count"):
            kids = sorted(children(n["path"]), key=lambda c: -((c.get("tree") or {}).get("md_bytes") or 0))
            for c in kids[:a.top]:
                show(c, depth - 1, ind + "  ")
            if len(kids) > a.top:
                print(f"{ind}  … {len(kids) - a.top} more")
    show(node, a.depth, "")
    return 0


def cmd_status(a) -> int:
    st = load(Path(a.dir))
    if not st:
        sys.exit("no copy here")
    cur = get_json("/api/v1")["release"]
    print(json.dumps({k: v for k, v in st.items() if k != "etags"}, indent=1))
    print(f"current release: {cur}" + ("" if cur == st["release"] else f" — run: pramana_sync.py update {a.dir}"))
    return 0


def main(argv=None) -> int:
    global BASE
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=BASE, help=f"the site (default {BASE})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="download a dump into DIR")
    p.add_argument("dir")
    p.add_argument("--parts", nargs="+", help="only these paths (in.veda, inf …); default: everything")
    p.add_argument("--release", help="default: the latest")
    p.add_argument("--form", default="md", choices=["md", "jsonl"], help="jsonl: keep the .jsonl.zst parts instead")
    p.add_argument("--dumps", default="", help="where the dumps are (default: the API's /api/v1/dumps; a URL or a directory)")
    p.add_argument("--keep", action="store_true", help="keep the downloaded archives (DIR/.downloads)")
    p.add_argument("--open-only", action="store_true", help="only texts under an open licence (text.md of the others left out)")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("update", help="apply the changes since the copy's release")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser("mirror", help="copy a subtree from the API")
    p.add_argument("dir")
    p.add_argument("path")
    p.add_argument("--passages", action="store_true", help="also every passage as its own file (_passages/)")
    p.add_argument("--open-only", action="store_true", help="only texts under an open licence")
    p.set_defaults(fn=cmd_mirror)
    p = sub.add_parser("plan", help="sizes across the tree")
    p.add_argument("path", nargs="?", default="")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--top", type=int, default=40)
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("status")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_status)
    a = ap.parse_args(argv)
    BASE = a.base.rstrip("/")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
