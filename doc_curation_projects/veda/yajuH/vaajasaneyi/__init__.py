import glob
import logging
import os
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile


SAMHITA_DIR_STATIC = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/"
MULA_DIR = os.path.join(SAMHITA_DIR_STATIC, "mUlam_VH")
TIKA_DIR = os.path.join(SAMHITA_DIR_STATIC, "sarvASh_TIkAH")