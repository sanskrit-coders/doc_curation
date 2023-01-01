import glob
import logging
import os
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile


SAMHITA_DIR_STATIC = "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/static/kauthumam/saMhitA"
MULA_DIR = os.path.join(SAMHITA_DIR_STATIC, "mUlam")
TIKA_DIR = os.path.join(SAMHITA_DIR_STATIC, "sarvASh_TIkAH")


def rk_num_from_path(Rk_path):
  id_match = regex.match(".+?_(\d{4})_", os.path.basename(Rk_path))
  if id_match is None:
    logging.error(Rk_path)
  return id_match.group(1)



def rk_id_from_path(Rk_path):
  Rk_id = regex.sub(".*mUlam/(.+/[^/]+_.+).md", "", Rk_path)
  return Rk_id


@lru_cache
def get_Rk_id_to_name_map_from_muulam():
  Rk_paths = glob.glob(os.path.join(SAMHITA_DIR_STATIC, "mUlam/**/*.md"), recursive=True)
  Rk_paths = sorted(Rk_paths)
  Rk_id_to_name_map = {}
  Rk_num_to_name_map = {}
  for Rk_path in Rk_paths:
    Rk_id_numerical = rk_num_from_path(Rk_path)
    Rk_id = rk_id_from_path(Rk_path)
    Rk_path = regex.sub(".*mUlam/", "", Rk_path).replace(".md", "")
    Rk_num_to_name_map[Rk_id_numerical] = Rk_path
    Rk_id_to_name_map[Rk_id_numerical] = Rk_path
  return (Rk_id_to_name_map, Rk_num_to_name_map)