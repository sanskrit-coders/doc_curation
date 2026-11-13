import os

VISHVASA_DIR  = os.path.expanduser("~/gitland/vishvAsa")
SITE_BASE     = "https://vishvasa.github.io/"


def md_to_site_path(md_path, site_base=SITE_BASE):
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
    return site_base + md_path


from . import appscript_client  # noqa: F401, E402
from . import local_library  # noqa: F401, E402
