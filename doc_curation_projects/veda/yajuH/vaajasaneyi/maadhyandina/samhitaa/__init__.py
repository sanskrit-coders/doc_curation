import glob
import os
from functools import lru_cache

static_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "mUlam")



def mantra_id_from_path(mantra_path):
  mantra_name = os.path.basename(mantra_path).replace(".md", "")
  return "/".join(mantra_path.split("/")[-3:-1]) + "/" + mantra_name.split("_")[0]


def chapter_id_from_path(mantra_path):
  return mantra_path.split("/")[-1]


@lru_cache
def get_mantras(chapter_id):
  mantra_paths = glob.glob(os.path.join(ref_dir, f"{chapter_id:02d}/*.md"), recursive=False)
  mantra_paths = sorted(mantra_paths)
  return mantra_paths