"""Local helper CLI to stage Markdown directories to Kaggle, run ``infer_batch.py``,
and apply post-guarded outputs back to the workspace."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from doc_curation.llm.proofreader.guards import (
  enforce_post_guards,
  mask_protected_blocks,
  restore_protected_blocks,
)

KAGGLE_BIN = os.environ.get("KAGGLE_BIN") or shutil.which("kaggle") or os.path.expanduser("~/.local/bin/kaggle")
DEFAULT_ADAPTER_DATASET = "vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora"
DEFAULT_LOCAL_ADAPTER_DIR = str(
  Path(__file__).resolve().parents[3] / "data" / "models" / "qwen3-14b-sanskrit-lora"
)


def stage_batch_dataset(
  src_dir: str,
  staging_dir: str,
  dataset_id: str,
  *,
  clause_newlines: bool = True,
  suggest_corrections: bool = True,
  extra_instructions: str = "",
  base_model: str = "Qwen/Qwen3-14B",
) -> Path:
  """Stage ``.md`` files + ``job_config.json`` + ``dataset-metadata.json``."""
  st = Path(staging_dir)
  if st.exists():
    shutil.rmtree(st)
  st.mkdir(parents=True)

  src = Path(src_dir)
  files = [src] if src.is_file() else [p for p in src.rglob("*.md") if p.name != "_index.md"]
  for p in files:
    rel = p.name if src.is_file() else p.relative_to(src)
    dest = st / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)

  (st / "job_config.json").write_text(
    json.dumps(
      {
        "clause_newlines": clause_newlines,
        "suggest_corrections": suggest_corrections,
        "extra_instructions": extra_instructions,
        "base_model": base_model,
      },
      indent=2,
      ensure_ascii=False,
    ),
    encoding="utf-8",
  )
  (st / "dataset-metadata.json").write_text(
    json.dumps(
      {
        "title": dataset_id.split("/")[-1],
        "id": dataset_id,
        "licenses": [{"name": "CC0-1.0"}],
      },
      indent=2,
    ),
    encoding="utf-8",
  )
  return st


def apply_downloaded_outputs(
  src_dir: str,
  downloaded_out_dir: str,
  *,
  allow_suggestions: bool = True,
) -> list[str]:
  """Verify and apply downloaded ``out_md/`` files over ``src_dir`` with post-guards."""
  src = Path(src_dir)
  out_root = Path(downloaded_out_dir)
  updated: list[str] = []
  for out_fp in sorted(out_root.rglob("*.md")):
    rel = out_fp.relative_to(out_root)
    orig_fp = src if src.is_file() else (src / rel)
    if not orig_fp.is_file():
      continue
    orig_txt = orig_fp.read_text(encoding="utf-8")
    gen_txt = out_fp.read_text(encoding="utf-8")
    masked_orig, masks = mask_protected_blocks(orig_txt)
    masked_gen, _ = mask_protected_blocks(gen_txt)
    guarded = enforce_post_guards(masked_orig, masked_gen, allow_suggestions=allow_suggestions)
    final_txt = restore_protected_blocks(guarded, masks)
    orig_fp.write_text(final_txt, encoding="utf-8")
    updated.append(str(orig_fp))
  return updated


def publish_lora_dataset(
  downloaded_kernel_out: str,
  dataset_id: str = DEFAULT_ADAPTER_DATASET,
  version_msg: str = "Trained Qwen3-14B Sanskrit proofreader/interleaver LoRA",
) -> Path:
  """Package ``adapter/`` + ``eval_report.json`` from kernel output as a Kaggle Dataset."""
  out_dir = Path(downloaded_kernel_out)
  adapter_dir = out_dir / "adapter"
  if not (adapter_dir / "adapter_config.json").is_file():
    raise FileNotFoundError(f"Missing adapter_config.json in {adapter_dir}")

  report_src = out_dir / "eval_report.json"
  if report_src.is_file():
    shutil.copy2(report_src, adapter_dir / "eval_report.json")

  # Rename PEFT's auto-generated README.md to MODEL_CARD.md so Kaggle datasets API doesn't reject it
  readme_fp = adapter_dir / "README.md"
  if readme_fp.is_file():
    readme_fp.replace(adapter_dir / "MODEL_CARD.md")

  (adapter_dir / "dataset-metadata.json").write_text(
    json.dumps(
      {
        "title": dataset_id.split("/")[-1],
        "id": dataset_id,
        "licenses": [{"name": "CC0-1.0"}],
      },
      indent=2,
    ),
    encoding="utf-8",
  )

  chk = subprocess.run([KAGGLE_BIN, "datasets", "status", dataset_id], capture_output=True, text=True)
  if chk.returncode == 0 and "ready" in chk.stdout.lower():
    subprocess.check_call([KAGGLE_BIN, "datasets", "version", "-p", str(adapter_dir), "-m", version_msg, "--dir-mode", "zip"])
  else:
    subprocess.check_call([KAGGLE_BIN, "datasets", "create", "-p", str(adapter_dir), "--dir-mode", "zip"])
  return adapter_dir


def save_adapter_locally(
  downloaded_kernel_out: str,
  dest_dir: str = DEFAULT_LOCAL_ADAPTER_DIR,
) -> Path:
  """Persist trained LoRA ``adapter/`` + ``eval_report.json`` into the local workspace
  (with a ``.gitignore`` excluding large binary ``*.safetensors`` and ``tokenizer.json``)."""
  out_dir = Path(downloaded_kernel_out)
  adapter_src = out_dir / "adapter" if (out_dir / "adapter" / "adapter_config.json").is_file() else out_dir
  if not (adapter_src / "adapter_config.json").is_file():
    raise FileNotFoundError(f"Missing adapter_config.json in {adapter_src}")

  dest = Path(dest_dir)
  dest.mkdir(parents=True, exist_ok=True)
  for item in adapter_src.iterdir():
    if item.is_file() and item.name != "dataset-metadata.json":
      target_name = "MODEL_CARD.md" if item.name == "README.md" else item.name
      shutil.copy2(item, dest / target_name)

  report_src = out_dir / "eval_report.json"
  if report_src.is_file():
    shutil.copy2(report_src, dest / "eval_report.json")

  (dest / ".gitignore").write_text("*.safetensors\ntokenizer.json\n", encoding="utf-8")
  return dest


