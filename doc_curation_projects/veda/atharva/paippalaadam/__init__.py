import glob
import logging
import os
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile


SAMHITA_DIR_STATIC = "/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/paippalAdam/saMhitA/"
MULA_DIR = os.path.join(SAMHITA_DIR_STATIC, "mUlam")
TIKA_DIR = os.path.join(SAMHITA_DIR_STATIC, "sarvASh_TIkAH")
CONTENT_DIR = os.path.join(SAMHITA_DIR_STATIC.replace("static", "content"), "sarva-prastutiH")


def rk_id_from_path(Rk_path):
  Rk_name = os.path.basename(Rk_path).replace(".md", "")
  path_parts = Rk_path.split("/")
  return "/".join([path_parts[-3], path_parts[-2].split("_")[0], Rk_name.split("_")[0]])


def suukta_id_from_path(Rk_path):
  return "/".join(Rk_path.split("/")[-3:-1])


@lru_cache
def get_Rk_id_to_name_map_from_muulam():
  Rk_paths = glob.glob(os.path.join(SAMHITA_DIR_STATIC, "mUlam/*/*/*.md"), recursive=True)
  Rk_paths = sorted(Rk_paths)
  Rk_id_to_name_map = {}
  for Rk_path in Rk_paths:
    Rk_id_numerical = rk_id_from_path(Rk_path)
    Rk_path = regex.sub(".*mUlam/", "", Rk_path).replace(".md", "")
    Rk_id_to_name_map[Rk_id_numerical] = Rk_path
  return Rk_id_to_name_map


def get_suukta_id_to_rk_map():
  suukta_id_to_rk_map = {}
  for kaanda_index in range(1, 21):
    kaanda_id = f"{kaanda_index:02}"
    suukta_ids = [f"{kaanda_id}/{x}" for x in os.listdir(os.path.join(MULA_DIR, kaanda_id)) if x != "_index.md"]
    for suukta_id in suukta_ids:
      rk_ids = [f"{suukta_id}/{x}" for x in os.listdir(os.path.join(MULA_DIR, suukta_id)) if x != "_index.md"]
      suukta_id_to_rk_map[suukta_id] = sorted(rk_ids)
  return suukta_id_to_rk_map
