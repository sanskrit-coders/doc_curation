"""Kaggle 2×T4 QLoRA training & benchmark script for Sanskrit Proofreader/Interleaver.

Key T4 memory optimizations for 14B large-vocab (151,936) models:
1. Keeps frozen ``embed_tokens`` & ``lm_head`` in ``float16`` (prevents ``prepare_model_for_kbit_training``
   from burning 3.1 GiB extra VRAM upcasting frozen 778M-param ``lm_head`` to FP32),
   while keeping trainable LoRA master weights strictly in ``float32`` during training
   and casting them to ``float16`` when saving the final adapter (~123 MB).
2. Slices ``hidden_states`` to ONLY supervised completion tokens (``labels != -100``)
   before projecting through ``lm_head`` in 128-token checkpointed chunks — cutting
   vocab-logit VRAM from ~2.8 GiB down to <80 MiB with mathematically identical gradients.
"""
from __future__ import annotations

import os as _early_os
_early_os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import difflib
import json
import math
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

_CANONICAL_CLAUSE_ON_PROMPT = """You are an expert Sanskrit proofreader, sandhi-preserving hyphenator, and Markdown formatter.

### Sanskrit Separation & Hyphenation Rules
1. **Inline cardinal rule — never revert sandhi within a line:** Within a single line, split the *surface result* of sandhi; never undo it. (Reverting external sandhi across a syntactic phrase, clause, or quote newline IS allowed — see Sentence & Phrase Line Breaks below.)
2. **Absolute inline veto — non-separable vowel mergers stay joined inline:** Within a line, never split dīrgha (`आ`, `ई`, `ऊ`, `ॠ`), guṇa (`ए`, `ओ`), or vṛddhi (`ऐ`, `औ`) vowel mergers with a space or hyphen, even inside a samāsa (`धर्मार्थ`, `स्वप्रकाशाद्वितीय`, `महोत्सव`, `रामेति`, `सदैव` MUST stay joined inline).
3. **Separable boundaries MUST be split** (when not vetoed inline):
   - **yaṇ sandhi (`य्`, `व्`):** Keep the semivowel with the left piece (`इत्येवम्` → `इत्य् एवम्`, `मध्वरिः` → `मध्व्-अरिः`).
   - **Visarga sandhi:** `रामोऽस्ति` → `रामो ऽस्ति` (keep `ऽ` attached to right word), `दुष्प्रकृतेरस्य` → `दुष्प्रकृतेर् अस्य`, `नमस्ते` → `नमस् ते`.
   - **Final `म्` before vowel:** `फलमश्नुते` → `फलम् अश्नुते`, `अर्थमिति` → `अर्थम् इति`.
   - **Consonant assimilation:** `तद्धि` → `तद् धि`, `आश्रितत्वाच्च` → `आश्रितत्वाच् च`, `जगत्कारणम्` → `जगत्-कारणम्`.
   - **Plain samāsa concatenation:** Insert `-` between separable compound members (`हेतु-भावे`, `पुण्य-पापैः`), and `–` at major upapada seams inside nested compounds (`पेटिका-भेद–तत्-सङ्गती`). Keep single inflected words and primary/secondary suffixes (`-त्व`, `-तम्`, `-तस्`, `-मान`, `-सीत`) whole (`वृत्तस्य`, `क्षणिकत्वम्`, `हिततमम्`).
4. **Embedded Sanskrit:** Apply these rules to every Sanskrit segment (Devanāgarī, Roman/IAST, Kannada, etc.) even when embedded inside English or other-language prose; never hyphenate surrounding non-Sanskrit words.

### Source Errors & Doubtful Readings
- Settle editorial fixes before hyphenation: suggest clear OCR, spelling, diacritic, or grammatical errors in source words inline as `[[OLD|NEW]]` (e.g., `[[प्रारब्वं|प्रारब्धं]]`, `[[prarabvaṁ|prārabdhaṁ]]`), hyphenating `NEW` properly.
- Never silently alter source words without `[[OLD|NEW]]`, and never break a line inside `[[OLD|NEW]]`.
- Never guess at illegible garbage: mark the minimal illegible span as `[[??]]`.

### Sentence & Syntactic Phrase / Clause Line Breaks
- **Sentence breaks within a paragraph:** End each prose sentence (`।`, `॥`, `?`, `!`, `;`) with two trailing spaces and a newline (`  ` soft break); use blank lines (`\n\n`) only between distinct paragraphs, blockquotes (`>`), or blocks. Insert an omitted `।` + soft break when syntax clearly shows two disjoint sentences or commentary glosses fused without punctuation (e.g. `पित्रा सवित्रा।  ` before an independent clause), never mid-clause.
- **Intra-sentence phrase/clause breaks:** Separate distinct syntactic clauses onto lines ended with two trailing spaces (`  `): absolutive/gerundial phrases (`-त्वा`, `-य`), causal ablatives (`-त्वात्`, `-आत्`), locative absolutes (*sati saptamī*), participial phrases (`-अन्`, `-मानः`), quotative `इति` / correlative `यत्`-`तत्` clauses, and major `–` seams in multi-clause compound chains.
- **Breaking external sandhi across phrase/clause/quote newlines:** Prefer non-reverting splits at separable seams (`निश्चयादयं` → `निश्चयाद्  ` + newline + `अयं`, `ब्रह्मणोऽभिधेयतया` → `ब्रह्मणो  ` + newline + `ऽभिधेयतया`). When external sandhi (`dīrgha`, `guṇa`, `vṛddhi`, `yaṇ`, or `visarga`) fuses two distinct clauses, a `>` blockquote boundary, or a trailing `इति`/locative-absolute clause, revert the sandhi across the newline (never inline): e.g. `निश्चिते सतीक्षणादयः` → `निश्चिते सति  ` + newline + `ईक्षणादयः`; `भवतीति` → `भवति  ` + newline + `इति`; `प्रधानस्याचेतनस्यैवंरूपो` → `प्रधानस्याचेतनस्य  ` + newline + `एवं-रूपो`; `पृष्टो मृत्युस्तस्यार्थस्य` → `पृष्टो मृत्युः  ` + newline + `तस्यार्थस्य`.
- **Do not over-split:** Keep short single-clause sentences on one line; never break inside a tight noun-modifier pair, inside a single compound unit, inside `[[OLD|NEW]]`, or strand clitics (`च`, `वा`, `अपि`, `एव`, `हि`, `न`, `तु`) alone on a line.

### Output Rules
- Preserve any `<details><summary>मूलम्...</summary>...</details>`, `<<MULAM_...>>`, and `<!-- ... -->` markers verbatim.
- Output ONLY the processed text with no surrounding markdown code fences or chatter."""


def ensure_deps():
  needed = []
  for pkg in ("bitsandbytes", "peft", "accelerate"):
    try:
      __import__(pkg)
    except ImportError:
      needed.append(pkg)
  if needed:
    print(f"[setup] Installing {needed}...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", *needed])


def find_paths(explicit_data: str | None, explicit_resume: str | None) -> tuple[Path, Path | None]:
  data_dir = Path(explicit_data) if (explicit_data and os.path.isdir(explicit_data)) else None
  if data_dir is None:
    for root in ("/kaggle/input", "."):
      if os.path.isdir(root):
        for dp, _, fns in os.walk(root):
          if "train.jsonl" in fns and "eval.jsonl" in fns:
            data_dir = Path(dp)
            break
      if data_dir is not None:
        break
  if data_dir is None:
    raise FileNotFoundError("Could not locate train.jsonl and eval.jsonl under /kaggle/input")

  resume_dir = None
  if explicit_resume and os.path.isfile(os.path.join(explicit_resume, "adapter_config.json")):
    resume_dir = Path(explicit_resume)
  elif os.path.isdir("/kaggle/input"):
    for dp, _, fns in os.walk("/kaggle/input"):
      if "adapter_config.json" in fns:
        resume_dir = Path(dp)
        break
  return data_dir, resume_dir


def load_jsonl(path: Path) -> list[dict]:
  with open(path, encoding="utf-8") as f:
    return [json.loads(line) for line in f if line.strip()]


def build_tokenized_samples(records: list[dict], tokenizer, max_seq_len: int) -> list[dict]:
  samples, skipped_long = [], 0
  for rec in records:
    msgs = rec["messages"]
    prompt_str = tokenizer.apply_chat_template(
      msgs[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    full_str = tokenizer.apply_chat_template(
      msgs, tokenize=False, add_generation_prompt=False, enable_thinking=False
    )
    prompt_ids = tokenizer(prompt_str, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full_str, add_special_tokens=False)["input_ids"]
    if len(full_ids) > max_seq_len:
      skipped_long += 1
      continue
    if len(full_ids) <= len(prompt_ids) + 1:
      continue
    samples.append(
      {
        "input_ids": full_ids,
        "labels": [-100] * len(prompt_ids) + full_ids[len(prompt_ids):],
        "task_type": rec.get("task_type", "unknown"),
      }
    )
  print(
    f"[data] Tokenized {len(samples)}/{len(records)} samples "
    f"(skipped {skipped_long} > {max_seq_len} tokens)",
    flush=True,
  )
  return samples


def collate_batch(batch: list[dict], pad_id: int, torch_mod):
  max_len = ((max(len(x["input_ids"]) for x in batch) + 7) // 8) * 8
  input_ids, attn_mask, labels = [], [], []
  for x in batch:
    pad_n = max_len - len(x["input_ids"])
    input_ids.append(x["input_ids"] + [pad_id] * pad_n)
    attn_mask.append([1] * len(x["input_ids"]) + [0] * pad_n)
    labels.append(x["labels"] + [-100] * pad_n)
  return {
    "input_ids": torch_mod.tensor(input_ids, dtype=torch_mod.long),
    "attention_mask": torch_mod.tensor(attn_mask, dtype=torch_mod.long),
    "labels": torch_mod.tensor(labels, dtype=torch_mod.long),
  }


def compute_masked_completion_loss(peft_model, batch_tensors: dict, torch_mod, chunk_tokens: int = 128):
  """Run transformer backbone and project ONLY supervised completion tokens (labels != -100)
  through ``lm_head`` in small chunks, avoiding 2.8 GiB full-sequence vocab logits."""
  import torch.nn.functional as F
  from torch.utils.checkpoint import checkpoint

  causal_lm = peft_model.get_base_model()
  backbone_out = causal_lm.model(
    input_ids=batch_tensors["input_ids"],
    attention_mask=batch_tensors["attention_mask"],
    use_cache=False,
  )
  hidden = backbone_out[0]
  shift_hidden = hidden[:, :-1, :].reshape(-1, hidden.size(-1))
  shift_labels = batch_tensors["labels"][:, 1:].reshape(-1).to(shift_hidden.device)
  valid_mask = shift_labels != -100
  n_valid = int(valid_mask.sum().item())
  if n_valid == 0:
    return shift_hidden.sum() * 0.0

  lm_head = causal_lm.lm_head
  head_dev = lm_head.weight.device
  active_h = shift_hidden[valid_mask].to(head_dev)
  active_y = shift_labels[valid_mask].to(head_dev)

  def _chunk_ce(h_part, y_part):
    logits = lm_head(h_part).float()
    return F.cross_entropy(logits, y_part, reduction="sum")

  total_ce = active_h.new_zeros((), dtype=torch_mod.float32)
  for start in range(0, n_valid, chunk_tokens):
    h_c = active_h[start:start + chunk_tokens]
    y_c = active_y[start:start + chunk_tokens]
    total_ce = total_ce + checkpoint(_chunk_ce, h_c, y_c, use_reentrant=False)
  return total_ce / float(n_valid)


def generate_replies_batch(
  model,
  tokenizer,
  messages_list: list[list[dict]],
  torch_mod,
  max_new_tokens: int = 512,
  gen_batch_size: int = 6,
) -> list[str]:
  """Batched left-padded greedy decoding for 5x-6x faster T4 evaluation."""
  if not messages_list:
    return []
  orig_side = tokenizer.padding_side
  tokenizer.padding_side = "left"
  first_dev = next(model.parameters()).device
  eos_ids = sorted({
    t for t in (
      tokenizer.eos_token_id,
      tokenizer.convert_tokens_to_ids("<|im_end|>"),
      tokenizer.convert_tokens_to_ids("<|endoftext|>"),
    )
    if isinstance(t, int) and t >= 0
  })
  results: list[str] = []
  try:
    for st in range(0, len(messages_list), gen_batch_size):
      sub = messages_list[st:st + gen_batch_size]
      prompts = [
        tokenizer.apply_chat_template(
          m, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        for m in sub
      ]
      enc = tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False)
      inp_len = enc["input_ids"].shape[1]
      user_lens = [len(tokenizer(m[-1]["content"], add_special_tokens=False)["input_ids"]) for m in sub]
      dyn_max = min(max_new_tokens, max(64, int(max(user_lens) * 1.45) + 32))
      inputs = {k: v.to(first_dev) for k, v in enc.items()}
      with torch_mod.no_grad(), torch_mod.amp.autocast("cuda", dtype=torch_mod.float16):
        out_ids = model.generate(
          **inputs,
          max_new_tokens=dyn_max,
          do_sample=False,
          temperature=None,
          top_p=None,
          top_k=None,
          pad_token_id=tokenizer.pad_token_id,
          eos_token_id=eos_ids,
        )
      for row in out_ids:
        raw_dec = tokenizer.decode(row[inp_len:], skip_special_tokens=False)
        for stop_tok in ("<|im_end|>", "<|endoftext|>", "<|im_start|>"):
          if stop_tok in raw_dec:
            raw_dec = raw_dec.split(stop_tok, 1)[0]
        text = raw_dec.strip()
        if text.startswith("<think>") and "</think>" in text:
          text = text.split("</think>", 1)[1].strip()
        results.append(text)
  finally:
    tokenizer.padding_side = orig_side
  return results


class _NullCtx:
  def __enter__(self):
    return None

  def __exit__(self, *exc):
    return False


class _BenchmarkSuite:
  """Zero-shot vs fine-tuned LoRA benchmark suite."""

  def __init__(self, model, tokenizer, torch_mod, max_per_task: int):
    self.model = model
    self.tokenizer = tokenizer
    self.torch = torch_mod
    self.max_per_task = max_per_task

  def eval_updated_skill_probe(self) -> dict:
    probes = [
      "तत्र धर्मार्थकामानां कारणविशेषे निश्चिते सतीक्षणादयः प्रवर्तन्त इति सिद्धम्।",
      "अत्र प्रधानस्याचेतनस्यैवंरूपो जगत्कारणभावो नोपपद्यत इत्याह।",
      "पृष्टो मृत्युस्तस्यार्थस्य निर्णयाय स्वप्रकाशाद्वितीयमात्मानमुपदिदेश।",
    ]
    out = {}
    for mode_name, disable_lora in (("base_zero_shot", True), ("finetuned_lora", False)):
      with (self.model.disable_adapter() if disable_lora else _NullCtx()):
        msgs = [
          [{"role": "system", "content": _CANONICAL_CLAUSE_ON_PROMPT}, {"role": "user", "content": p}]
          for p in probes
        ]
        preds = generate_replies_batch(self.model, self.tokenizer, msgs, self.torch, 256, 3)
        inline_mergers_intact = int("धर्मार्थ" in preds[0] and "स्वप्रकाशाद्वितीय" in preds[2])
        no_newline_in_brackets = int(all("\n" not in m for p in preds for m in re.findall(r"\[\[[^\]]+\]\]", p)))
        has_clause_breaks = sum(int("\n" in p) for p in preds)
        out[mode_name] = {
          "inline_mergers_intact": bool(inline_mergers_intact),
          "no_newline_inside_brackets": bool(no_newline_in_brackets),
          "multiline_clause_count": f"{has_clause_breaks}/{len(probes)}",
          "outputs": preds,
        }
    return {"updated_skill_probe": out}

  def eval_hyphenations_toml(self, toml_path: Path) -> dict:
    with open(toml_path, "rb") as f:
      hyp_cfg = tomllib.load(f)
    sys_hyp = (
      "You are an expert Sanskrit proofreader, sandhi-preserving hyphenator, and Markdown formatter.\n\n"
      "### Sanskrit Separation & Hyphenation Rules\n"
      "1. **Never revert sandhi:** Split the *surface result* of sandhi; never undo sandhi.\n"
      "2. **Absolute Veto — Non-separable vowel mergers stay joined:** Never split "
      "dīrgha (`आ`, `ई`, `ऊ`, `ॠ`), guṇa (`ए`, `ओ`), or vṛddhi (`ऐ`, `औ`) vowel mergers, "
      "even inside a samāsa (e.g., `धर्मार्थ`, `स्वप्रकाशाद्वितीय`, `महोत्सव`, `रामेति`, `सदैव` MUST stay joined).\n"
      "3. **Separable boundaries MUST be split**: yaṇ (`इत्येवम्` → `इत्य् एवम्`, `मध्वरिः` → `मध्व्-अरिः`), "
      "visarga (`रामोऽस्ति` → `रामो ऽस्ति`, `नमस्ते` → `नमस् ते`), final `म्` before vowel (`फलमश्नुते` → `फलम् अश्नुते`), "
      "consonant assimilation (`तद्धि` → `तद् धि`, `जगत्कारणम्` → `जगत्-कारणम्`), and plain samāsa (`हेतु-भावे`).\n\n"
      "### Source Words Policy\n"
      "- Do NOT alter source characters or emit `[[OLD|NEW]]` editorial suggestions; perform separation and hyphenation only.\n"
      "- Output ONLY the processed text with no surrounding markdown code fences or chatter."
    )
    sections = (
      "non_separable_mergers", "yan_sandhi", "visarga_sandhi",
      "final_m_sandhi", "consonant_assimilation", "samasa_and_inflected_words", "bad_split_regressions",
    )
    cases = [(s, c["input"], c["expected"]) for s in sections for c in hyp_cfg.get(s, {}).get("cases", [])]
    if self.max_per_task < 10:
      mergers = [x for x in cases if x[0] == "non_separable_mergers"]
      others = [x for x in cases if x[0] != "non_separable_mergers"][:max(4, self.max_per_task * 2)]
      cases = mergers + others

    out = {}
    for mode_name, disable_lora in (("base_zero_shot", True), ("finetuned_lora", False)):
      exact_ok, seg_ok, merger_ok, merger_tot, diffs = 0, 0, 0, 0, []
      with (self.model.disable_adapter() if disable_lora else _NullCtx()):
        msgs_all = [[{"role": "system", "content": sys_hyp}, {"role": "user", "content": inp}] for _, inp, _ in cases]
        preds = generate_replies_batch(self.model, self.tokenizer, msgs_all, self.torch, max_new_tokens=96, gen_batch_size=8)
        for (sec, inp, exp), pred in zip(cases, preds):
          exact_ok += int(pred == exp)
          seg_ok += int([p for p in re.split(r"[ \-\u2013\u2014]+", pred.strip()) if p] == [p for p in re.split(r"[ \-\u2013\u2014]+", exp.strip()) if p])
          if sec == "non_separable_mergers":
            merger_tot += 1
            merger_ok += int(pred == exp)
          if pred != exp and len(diffs) < 10:
            diffs.append({"sec": sec, "in": inp, "exp": exp, "pred": pred})
      out[f"hyphenations_toml_{mode_name}"] = {
        "total": len(cases),
        "exact_acc": round(exact_ok / max(1, len(cases)), 4),
        "segment_acc": round(seg_ok / max(1, len(cases)), 4),
        "merger_veto_acc": round(merger_ok / max(1, merger_tot), 4),
        "sample_diffs": diffs,
      }
    return out

  def eval_heldout_tasks(self, eval_records: list[dict]) -> dict:
    by_task: dict[str, list[dict]] = {}
    for r in eval_records:
      by_task.setdefault(r["task_type"], []).append(r)

    out = {}
    for mode_name, disable_lora in (("base_zero_shot", True), ("finetuned_lora", False)):
      metrics: dict[str, dict] = {}
      with (self.model.disable_adapter() if disable_lora else _NullCtx()):
        cl_on = by_task.get("clause_newlines_on", [])[:self.max_per_task]
        cl_off = by_task.get("clause_newlines_off", [])[:self.max_per_task]
        if cl_on and cl_off:
          n_cl = min(len(cl_on), len(cl_off))
          preds_on = generate_replies_batch(self.model, self.tokenizer, [r["messages"][:-1] for r in cl_on[:n_cl]], self.torch, 384, 4)
          preds_off = generate_replies_batch(self.model, self.tokenizer, [r["messages"][:-1] for r in cl_off[:n_cl]], self.torch, 384, 4)
          on_ml = sum(int(p.count("\n") >= 1) for p in preds_on)
          off_sl = sum(int(p.count("\n") == 0) for p in preds_off)
          samples = [
            {"in": cl_on[k]["messages"][-2]["content"][:180], "on": preds_on[k][:220], "off": preds_off[k][:220]}
            for k in range(min(2, n_cl))
          ]
          metrics["clause_newline_instruction_following"] = {
            "n": n_cl,
            "clause_on_multiline_rate": round(on_ml / n_cl, 4),
            "clause_off_singleline_rate": round(off_sl / n_cl, 4),
            "samples": samples,
          }

        for jtask in ("translation_matcher", "commentary_interleaver"):
          sub = by_task.get(jtask, [])[:self.max_per_task]
          if not sub:
            continue
          preds = generate_replies_batch(self.model, self.tokenizer, [r["messages"][:-1] for r in sub], self.torch, 320, 4)
          v_json, ex_ok = 0, 0
          for r, pred in zip(sub, preds):
            gold = json.loads(r["messages"][-1]["content"])
            try:
              parsed = json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", pred.strip()))
              v_json += 1
              if jtask == "translation_matcher":
                ex_ok += int(parsed.get("starts") == gold.get("starts") and parsed.get("next_en") == gold.get("next_en"))
              else:
                ex_ok += int(parsed.get("assignments") == gold.get("assignments"))
            except Exception:
              pass
          metrics[jtask] = {"n": len(sub), "valid_json_rate": round(v_json / len(sub), 4), "exact_alignment_rate": round(ex_ok / len(sub), 4)}

        for stask in ("proofread_vp", "proofread_suggestions", "padapatha_accent"):
          sub = by_task.get(stask, [])[:self.max_per_task]
          if not sub:
            continue
          preds = generate_replies_batch(self.model, self.tokenizer, [r["messages"][:-1] for r in sub], self.torch, 512, 4)
          sims = [difflib.SequenceMatcher(a=r["messages"][-1]["content"], b=p).ratio() for r, p in zip(sub, preds)]
          sugs = sum(int("[[" in p and "|" in p) for p in preds)
          sample = {"gold": sub[0]["messages"][-1]["content"][:240], "pred": preds[0][:240]}
          metrics[stask] = {"n": len(sub), "avg_char_similarity": round(sum(sims) / len(sims), 4), "suggestion_rate": round(sugs / len(sub), 4), "sample": sample}
      out[f"heldout_tasks_{mode_name}"] = metrics
    return out


def load_qlora_model(args, resume_dir: Path | None, torch, n_gpus: int):
  from transformers import AutoModelForCausalLM, BitsAndBytesConfig
  from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training

  bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16
  )
  max_mem = {0: "11GiB", 1: "13GiB"} if n_gpus >= 2 else None
  model = AutoModelForCausalLM.from_pretrained(
    args.base_model,
    quantization_config=bnb_cfg,
    dtype=torch.float16,
    device_map="auto",
    max_memory=max_mem,
    attn_implementation="sdpa",
    trust_remote_code=True,
  )
  model.config.use_cache = False
  model = prepare_model_for_kbit_training(
    model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False}
  )
  if resume_dir is not None:
    print(f"[model] Warm-starting LoRA weights from {resume_dir}!", flush=True)
    model = PeftModel.from_pretrained(model, str(resume_dir), is_trainable=True)
  else:
    model = get_peft_model(
      model,
      LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
      ),
    )

  trainable_params = []
  for _, p in model.named_parameters():
    if p.requires_grad:
      p.data = p.data.float()
      trainable_params.append(p)
    elif p.dtype == torch.float32:
      p.data = p.data.to(torch.float16)
  model.print_trainable_parameters()
  torch.cuda.empty_cache()
  for i in range(n_gpus):
    print(f"[vram] GPU {i} allocated after load: {torch.cuda.memory_allocated(i) / (1024 ** 3):.2f} GiB", flush=True)
  return model, trainable_params


def run_training_loop(model, tokenizer, train_samples: list[dict], trainable_params: list, args, torch, bnb, n_gpus: int, rng) -> tuple[int, list[dict]]:
  steps_per_epoch = math.ceil(math.ceil(len(train_samples) / args.batch_size) / args.grad_accum)
  total_steps = args.max_steps if args.max_steps > 0 else max(1, int(steps_per_epoch * args.epochs))
  warmup_steps = max(1, int(0.06 * total_steps))
  optimizer = bnb.optim.PagedAdamW8bit(trainable_params, lr=args.lr, weight_decay=0.01)
  scaler = torch.amp.GradScaler("cuda", init_scale=1024.0)
  scheduler = torch.optim.lr_scheduler.LambdaLR(
    optimizer,
    lambda s: (s + 1) / warmup_steps if s < warmup_steps else max(0.1, 0.5 * (1.0 + math.cos(math.pi * (s - warmup_steps) / max(1, total_steps - warmup_steps)))),
  )

  os.makedirs(args.out_dir, exist_ok=True)
  first_dev = next(model.parameters()).device
  print(f"[train] Starting QLoRA: total_steps={total_steps} eff_batch={args.batch_size * args.grad_accum}", flush=True)

  model.train()
  opt_step, micro_idx, running_loss, valid_micro = 0, 0, 0.0, 0
  step_t0, loss_history = time.time(), []

  while opt_step < total_steps:
    epoch_samples = list(train_samples)
    rng.shuffle(epoch_samples)
    for w in range(0, len(epoch_samples), 64):
      epoch_samples[w:w + 64] = sorted(epoch_samples[w:w + 64], key=lambda x: len(x["input_ids"]))
    chunks = [epoch_samples[i:i + args.batch_size] for i in range(0, len(epoch_samples), args.batch_size)]
    rng.shuffle(chunks)
    for batch_items in chunks:
      bt = {k: v.to(first_dev, non_blocking=True) for k, v in collate_batch(batch_items, tokenizer.pad_token_id, torch).items()}
      with torch.amp.autocast("cuda", dtype=torch.float16):
        raw_loss = compute_masked_completion_loss(model, bt, torch)
        loss = raw_loss / args.grad_accum
      if torch.isfinite(loss):
        scaler.scale(loss).backward()
        running_loss += raw_loss.item()
        valid_micro += 1
      micro_idx += 1

      if micro_idx % args.grad_accum == 0:
        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        scheduler.step()
        opt_step += 1

        avg_loss, dt = running_loss / max(1, valid_micro), time.time() - step_t0
        loss_history.append({"step": opt_step, "loss": round(avg_loss, 4), "sec": round(dt, 2)})
        if opt_step <= 3 or opt_step % 10 == 0 or opt_step == total_steps:
          vram = [round(torch.cuda.max_memory_allocated(i) / (1024 ** 3), 2) for i in range(n_gpus)]
          print(f"[step {opt_step:03d}/{total_steps:03d}] loss={avg_loss:.4f} grad_norm={float(grad_norm):.3f} dt={dt:.1f}s peak_gib={vram}", flush=True)
        running_loss, valid_micro, step_t0 = 0.0, 0, time.time()

        if opt_step % 40 == 0 and opt_step < total_steps:
          model.save_pretrained(args.out_dir)
          tokenizer.save_pretrained(args.out_dir)
        if opt_step >= total_steps:
          break

  # Cast final LoRA weights to FP16 (~123 MB instead of 245 MB) before final save & eval
  for p in trainable_params:
    p.data = p.data.to(torch.float16)
  model.save_pretrained(args.out_dir)
  tokenizer.save_pretrained(args.out_dir)
  return total_steps, loss_history


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--base-model", default="Qwen/Qwen3-14B")
  ap.add_argument("--data-dir", default=None)
  ap.add_argument("--resume-adapter", default=None, help="Optional existing LoRA dir (auto-detected in /kaggle/input if present)")
  ap.add_argument("--out-dir", default="/kaggle/working/adapter")
  ap.add_argument("--max-seq-len", type=int, default=1408)
  ap.add_argument("--batch-size", type=int, default=2)
  ap.add_argument("--grad-accum", type=int, default=8)
  ap.add_argument("--lr", type=float, default=1.5e-4)
  ap.add_argument("--lora-r", type=int, default=16)
  ap.add_argument("--lora-alpha", type=int, default=32)
  ap.add_argument("--epochs", type=float, default=1.0)
  ap.add_argument("--max-steps", type=int, default=115)
  ap.add_argument("--eval-per-task", type=int, default=8)
  ap.add_argument("--seed", type=int, default=42)
  args = ap.parse_args()

  t0 = time.time()
  ensure_deps()

  import random
  import torch
  import bitsandbytes as bnb
  from transformers import AutoTokenizer

  rng = random.Random(args.seed)
  torch.manual_seed(args.seed)
  n_gpus = torch.cuda.device_count()
  print(f"[env] torch={torch.__version__} gpus={n_gpus} ({[torch.cuda.get_device_name(i) for i in range(n_gpus)]})", flush=True)

  data_dir, resume_dir = find_paths(args.data_dir, args.resume_adapter)
  train_records = load_jsonl(data_dir / "train.jsonl")
  eval_records = load_jsonl(data_dir / "eval.jsonl")
  tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
  if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token

  train_samples = build_tokenized_samples(train_records, tokenizer, args.max_seq_len)
  model, trainable_params = load_qlora_model(args, resume_dir, torch, n_gpus)
  total_steps, loss_history = run_training_loop(
    model, tokenizer, train_samples, trainable_params, args, torch, bnb, n_gpus, rng
  )

  model.eval()
  model.config.use_cache = True
  torch.cuda.empty_cache()
  print("[eval] Running Zero-Shot Base vs Fine-Tuned LoRA benchmarks...", flush=True)
  suite = _BenchmarkSuite(model, tokenizer, torch, args.eval_per_task)
  bench = {}
  if (data_dir / "hyphenations.toml").is_file():
    bench.update(suite.eval_hyphenations_toml(data_dir / "hyphenations.toml"))
  bench.update(suite.eval_updated_skill_probe())
  bench.update(suite.eval_heldout_tasks(eval_records))
  bench["training_meta"] = {
    "base_model": args.base_model, "total_steps": total_steps, "lora_r": args.lora_r,
    "elapsed_min": round((time.time() - t0) / 60.0, 2),
    "loss_curve_head": loss_history[:5], "loss_curve_tail": loss_history[-10:],
  }
  report_path = Path(args.out_dir).parent / "eval_report.json"
  report_path.write_text(json.dumps(bench, indent=2, ensure_ascii=False), encoding="utf-8")
  print(json.dumps(bench, indent=2, ensure_ascii=False)[:4500], flush=True)


if __name__ == "__main__":
  extra = os.environ.get("KAGGLE_TRAIN_ARGS", "").split()
  if extra and len(sys.argv) == 1:
    sys.argv.extend(extra)
  main()
