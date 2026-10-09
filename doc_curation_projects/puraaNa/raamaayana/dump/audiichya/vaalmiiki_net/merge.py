"""Merge valmikiramayan.net English commentaries into gorakhpur dest files.

Per-verse details are titled after the commentator:
  Ayodhya/Sundara/Yuddha -> "Murali Krishnamurthy Kopalle Murthy"
  Bala/Aranya/Kishkindha  -> "Desiraju Hanumanta Rao"
Sarga intros become "<author> - Intro"; shloka variants become "मूलम् - VR".

Usage:
  python merge.py [--dry-run] [--kandas 1,2,3,4,5,6] [--cache-dir DIR]
"""
import argparse
import logging
import os
import sys

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.INFO,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

from doc_curation.md.content_processor.commentary_merger import merge_valmiki_net

DEST_BASE = "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/goraxapura-pAThaH/hindy-anuvAdaH"
DEFAULT_CACHE = "/tmp/opencode/vr_cache"


def main(argv=None):
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument("--kandas", default="1,2,3,4,5,6",
                  help="comma-separated kanda numbers (1=Bala..6=Yuddha)")
  ap.add_argument("--cache-dir", default=DEFAULT_CACHE)
  ap.add_argument("--dest-base", default=DEST_BASE)
  args = ap.parse_args(argv)
  kandas = tuple(int(x) for x in args.kandas.split(",") if x.strip())
  totals = merge_valmiki_net(dest_base_dir=args.dest_base, cache_dir=args.cache_dir,
                             kandas=kandas, dry_run=args.dry_run)
  print(f"VR merge totals: {totals}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
