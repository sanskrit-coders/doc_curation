"""CLI entry point for ``python -m doc_curation.llm.proofreader.dataset``."""
import argparse
import json

from . import build_sft_datasets


def main() -> None:
  ap = argparse.ArgumentParser(description="Build Sanskrit Proofreader/Interleaver SFT JSONL dataset.")
  ap.add_argument("--out-dir", required=True)
  ap.add_argument("--seed", type=int, default=42)
  args = ap.parse_args()
  print(json.dumps(build_sft_datasets(args.out_dir, seed=args.seed), indent=2, ensure_ascii=False))


if __name__ == "__main__":
  main()
