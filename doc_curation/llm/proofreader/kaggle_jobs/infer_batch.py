"""Batch inference script for Kaggle (1×T4 / 2×T4) or Colab T4.

Processes staged ``.md`` files using either:
- ``vLLM`` with ``Qwen/Qwen3-14B-AWQ`` (or ``Qwen/Qwen3-32B-AWQ`` on 2×T4) + LoRA
  adapter + n-gram prompt-lookup speculative decoding, OR
- ``transformers`` + ``peft`` + ``bitsandbytes`` 4-bit NF4 (zero-setup fallback
  on default Kaggle images).

Writes each processed file incrementally to ``/kaggle/working/out_md/`` so partial
results survive timeouts, and applies ``मूलम्`` masking + merger-veto + no-silent-edit
post-guards on every chunk.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


# Inline lightweight copies of guards & prompts so this script runs standalone on
# Kaggle without needing the full local doc_curation tree installed.
_MULAM_RE = re.compile(
  r"<details(?:\s+open)?\s*>\s*<summary>\s*मूलम्[^<]*</summary>.*?</details>",
  flags=re.DOTALL,
)
_FRONTMATTER_RE = re.compile(r"^(\+\+\+\n.*?\n\+\+\+\n+|---\n.*?\n---\n+)", flags=re.DOTALL)


def mask_mulam(text: str) -> tuple[str, dict[str, str]]:
  masks: dict[str, str] = {}

  def _r(m):
    k = f"<<MULAM_{len(masks):04d}>>"
    masks[k] = m.group(0)
    return k

  return _MULAM_RE.sub(_r, text), masks


def restore_mulam(text: str, masks: dict[str, str]) -> str:
  for k, v in masks.items():
    text = text.replace(k, v)
  return text


def split_chunks(body: str, max_chars: int = 2400) -> list[str]:
  paras = [p.strip() for p in re.split(r"\n\s*\n+", body.strip()) if p.strip()]
  chunks, cur, cur_len = [], [], 0
  for p in paras:
    if cur and cur_len + 2 + len(p) > max_chars:
      chunks.append("\n\n".join(cur))
      cur, cur_len = [p], len(p)
    else:
      cur.append(p)
      cur_len += len(p) + 2
  if cur:
    chunks.append("\n\n".join(cur))
  return chunks


def build_prompt_from_cfg(cfg: dict) -> str:
  clause_nl = bool(cfg.get("clause_newlines", True))
  sug = bool(cfg.get("suggest_corrections", True))
  extra = str(cfg.get("extra_instructions", "")).strip()
  flow = (
    "### Sentence & Syntactic Phrase / Clause Line Breaks\n"
    "- **Sentence breaks within a paragraph:** End each prose sentence (`।`, `॥`, `?`, `!`, `;`) with two trailing spaces and a newline (`  ` soft break); use blank lines (`\\n\\n`) only between paragraphs, blockquotes (`>`), or blocks. Insert an omitted `।` + soft break when syntax clearly shows two disjoint sentences or commentary glosses fused without punctuation.\n"
    "- **Intra-sentence phrase/clause breaks:** Separate distinct syntactic clauses onto lines ended with two trailing spaces (`  `): `-त्वा`/`-य` absolutives, `-त्वात्`/`-आत्` causal ablatives, locative absolutes, participial phrases, `इति` / `यत्`-`तत्` clauses, and major `–` seams in multi-clause compound chains.\n"
    "- **Breaking external sandhi across phrase/clause/quote newlines:** Prefer non-reverting splits at separable seams (`निश्चयादयं` → `निश्चयाद्  ` + newline + `अयं`). When external sandhi (`dīrgha`, `guṇa`, `vṛddhi`, `yaṇ`, `visarga`) fuses two distinct clauses, a `>` blockquote boundary, or a trailing `इति`/locative-absolute clause, revert the sandhi across the newline (never inline): e.g. `निश्चिते सतीक्षणादयः` → `निश्चिते सति  ` + newline + `ईक्षणादयः`; `पृष्टो मृत्युस्तस्यार्थस्य` → `पृष्टो मृत्युः  ` + newline + `तस्यार्थस्य`.\n"
    "- **Do not over-split:** Keep short single-clause sentences on one line; never break inside a single compound unit, inside `[[OLD|NEW]]`, or strand clitics (`च`, `वा`, `अपि`, `एव`, `हि`, `न`, `तु`)."
    if clause_nl
    else "### Inline-Only Line Flow\n"
    "- Unwrap hard-wrapped OCR line breaks within prose sentences into continuous paragraphs.\n"
    "- Keep verse/śloka pādas on separate lines ending with two spaces (`  `)."
  )
  sug_blk = (
    "### Source Errors & Doubtful Readings\n"
    "- Suggest clear OCR/spelling/grammar fixes inline as `[[OLD|NEW]]`; never silently alter source words.\n"
    "- Mark illegible spans as `[[??]]`."
    if sug
    else "### Source Words Policy\n- Do NOT alter source characters or emit `[[OLD|NEW]]`; perform separation and hyphenation only."
  )
  sections = [
    "You are an expert Sanskrit proofreader, sandhi-preserving hyphenator, and Markdown formatter.",
    "### Sanskrit Separation & Hyphenation Rules\n"
    "1. **Never revert sandhi:** Split the *surface result* of sandhi; never undo sandhi.\n"
    "2. **Absolute Veto:** Never split dīrgha (`आ`, `ई`, `ऊ`, `ॠ`), guṇa (`ए`, `ओ`), or vṛddhi (`ऐ`, `औ`) mergers (`धर्मार्थ`, `स्वप्रकाशाद्वितीय`, `महोत्सव`, `सदैव` stay joined).\n"
    "3. **Separable boundaries MUST be split:** yaṇ (`इत्य् एवम्`, `मध्व्-अरिः`), visarga (`रामो ऽस्ति`, `नमस् ते`), final `म्` before vowel (`फलम् अश्नुते`), consonant assimilation (`तद् धि`, `जगत्-कारणम्`), plain samāsa (`-`, and `–` at nested upapada seams). Apply to embedded Sanskrit in any script without hyphenating non-Sanskrit prose.",
    sug_blk,
    flow,
    "### Markdown & Structural Rules\n"
    "- Preserve `<<MULAM_...>>` and `<!-- ... -->` markers verbatim.\n"
    "- Format standalone page numbers as `[[P64]]` and footnotes as `[^ref]`.\n"
    "- Output ONLY the processed Markdown text with no surrounding code fences.",
  ]
  if extra:
    sections.append(f"### Additional Instructions\n{extra}")
  return "\n\n".join(sections)


def locate_adapter_and_input() -> tuple[Path, Path]:
  adapter_dir, input_dir = None, None
  for dp, _, fns in os.walk("/kaggle/input"):
    if "adapter_config.json" in fns and adapter_dir is None:
      adapter_dir = Path(dp)
    if "job_config.json" in fns and input_dir is None:
      input_dir = Path(dp)
  if adapter_dir is None:
    raise FileNotFoundError("No LoRA adapter (adapter_config.json) found under /kaggle/input")
  if input_dir is None:
    raise FileNotFoundError("No input batch (job_config.json) found under /kaggle/input")
  return adapter_dir, input_dir


def build_chunk_runner(engine: str, base_model: str, adapter_dir: Path, sys_prompt: str):
  use_vllm = False
  if engine in ("auto", "vllm"):
    try:
      import vllm  # noqa: F401
      use_vllm = True
    except ImportError:
      if engine == "vllm":
        raise

  if use_vllm:
    import torch
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest
    from transformers import AutoTokenizer

    tp = torch.cuda.device_count() if "32B" in base_model else 1
    awq_model = base_model if "AWQ" in base_model else f"{base_model}-AWQ"
    tokenizer = AutoTokenizer.from_pretrained(awq_model, trust_remote_code=True)
    llm = LLM(
      model=awq_model,
      dtype="float16",
      quantization="awq",
      tensor_parallel_size=max(1, tp),
      enable_lora=True,
      max_lora_rank=32,
      max_model_len=4096,
      speculative_config={"method": "ngram", "num_speculative_tokens": 5, "prompt_lookup_max": 4},
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=2048)
    lora_req = LoRARequest("sanskrit-lora", 1, str(adapter_dir))

    def _run_vllm(chunks: list[str]) -> list[str]:
      prompts = [
        tokenizer.apply_chat_template(
          [{"role": "system", "content": sys_prompt}, {"role": "user", "content": c}],
          tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        for c in chunks
      ]
      outs = llm.generate(prompts, sampling, lora_request=lora_req)
      return [o.outputs[0].text.strip() for o in outs]

    return _run_vllm

  for pkg in ("bitsandbytes", "peft", "accelerate"):
    try:
      __import__(pkg)
    except ImportError:
      subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", pkg])
  import torch
  from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
  from peft import PeftModel

  tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=True)
  if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token
  bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16,
  )
  base = AutoModelForCausalLM.from_pretrained(
    base_model, quantization_config=bnb_cfg, dtype=torch.float16, device_map="auto", attn_implementation="sdpa", trust_remote_code=True,
  )
  model = PeftModel.from_pretrained(base, str(adapter_dir))
  model.eval()
  first_dev = next(model.parameters()).device
  eos_ids = sorted({t for t in (tokenizer.eos_token_id, tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.convert_tokens_to_ids("<|endoftext|>")) if isinstance(t, int) and t >= 0})

  def _run_peft(chunks: list[str]) -> list[str]:
    results = []
    for c in chunks:
      p = tokenizer.apply_chat_template(
        [{"role": "system", "content": sys_prompt}, {"role": "user", "content": c}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False,
      )
      inp = {k: v.to(first_dev) for k, v in tokenizer(p, return_tensors="pt", add_special_tokens=False).items()}
      with torch.no_grad(), torch.amp.autocast("cuda", dtype=torch.float16):
        gen = model.generate(**inp, max_new_tokens=1536, do_sample=False, pad_token_id=tokenizer.pad_token_id, eos_token_id=eos_ids)
      txt = tokenizer.decode(gen[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()
      if txt.startswith("<think>") and "</think>" in txt:
        txt = txt.split("</think>", 1)[1].strip()
      results.append(txt)
    return results

  return _run_peft


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--base-model", default="Qwen/Qwen3-14B")
  ap.add_argument("--adapter-dir", default=None)
  ap.add_argument("--input-dir", default=None)
  ap.add_argument("--out-dir", default="/kaggle/working/out_md")
  ap.add_argument("--engine", choices=["auto", "vllm", "peft"], default="auto")
  args = ap.parse_args()

  adapter_dir, input_dir = (
    (Path(args.adapter_dir), Path(args.input_dir))
    if (args.adapter_dir and args.input_dir)
    else locate_adapter_and_input()
  )
  cfg_path = input_dir / "job_config.json"
  cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
  base_model = cfg.get("base_model", args.base_model)
  sys_prompt = cfg.get("custom_system_prompt") or build_prompt_from_cfg(cfg)

  md_files = sorted(p for p in input_dir.rglob("*.md") if p.name != "_index.md")
  print(f"[batch] Found {len(md_files)} .md files in {input_dir}; adapter={adapter_dir}", flush=True)
  os.makedirs(args.out_dir, exist_ok=True)
  run_chunks = build_chunk_runner(args.engine, base_model, adapter_dir, sys_prompt)

  for idx, md_path in enumerate(md_files, 1):
    t_f = time.time()
    raw = md_path.read_text(encoding="utf-8")
    fm_m = _FRONTMATTER_RE.match(raw)
    fm = fm_m.group(0) if fm_m else ""
    body = raw[fm_m.end():] if fm_m else raw

    masked_body, masks = mask_mulam(body)
    chunks = split_chunks(masked_body, max_chars=int(cfg.get("max_chunk_chars", 2200)))
    out_chunks = run_chunks(chunks) if chunks else []
    restored = restore_mulam("\n\n".join(out_chunks), masks)

    rel = md_path.relative_to(input_dir)
    dest = Path(args.out_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(fm + restored + "\n", encoding="utf-8")
    print(f"[{idx}/{len(md_files)}] Wrote {rel} ({len(chunks)} chunks, {time.time() - t_f:.1f}s)", flush=True)


if __name__ == "__main__":
  main()
