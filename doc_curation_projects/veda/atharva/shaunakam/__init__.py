import glob
import logging
import os
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile


SAMHITA_DIR_STATIC = "/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA/"
VP_DIR = os.path.join(SAMHITA_DIR_STATIC, "vishvAsa-prastutiH")
TIKA_DIR = os.path.join(SAMHITA_DIR_STATIC, "sarvASh_TIkAH")


def rk_id_from_path(Rk_path):
  Rk_name = os.path.basename(Rk_path).replace(".md", "")
  path_parts = Rk_path.split("/")
  return "/".join([path_parts[-3], path_parts[-2].split("_")[0], Rk_name.split("_")[0]])


def suukta_id_from_path(Rk_path):
  return "/".join(Rk_path.split("/")[-3:-1])


@lru_cache
def get_Rk_id_to_name_map_from_muulam():
  Rk_paths = [
    p for p in glob.glob(os.path.join(SAMHITA_DIR_STATIC, "vishvAsa-prastutiH/*/*/*.md"), recursive=True)
    if not os.path.basename(p).startswith("_")
  ]
  Rk_paths = sorted(Rk_paths)
  Rk_id_to_name_map = {}
  for Rk_path in Rk_paths:
    Rk_id_numerical = rk_id_from_path(Rk_path)
    Rk_path = regex.sub(".*vishvAsa-prastutiH/", "", Rk_path).replace(".md", "")
    Rk_id_to_name_map[Rk_id_numerical] = Rk_path
  return Rk_id_to_name_map