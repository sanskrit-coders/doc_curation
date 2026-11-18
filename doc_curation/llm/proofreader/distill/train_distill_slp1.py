"""Kaggle 2×T4 Knowledge Distillation & ONNX Export for the Local SLP1 Hyphenator.

Pipeline:
1. Teacher Stage: Loads ``Qwen/Qwen3-14B`` + trained Sanskrit Proofreader LoRA adapter,
   runs batched greedy inference on uncurated ``मूलम्`` passages across śāstra/kāvya/purāṇa,
   filters strictly for 100% sandhi-skeleton fidelity, and encodes teacher pseudo-labels
   into phonemic Extended-SLP1 boundary sequences (upweighted 2×).
2. Student Stage: Trains an 8-layer Bidirectional SLP1 Conformer-Transformer (~7.9M params:
   Multi-Head Self-Attention + Depthwise-Separable 7-gram Phonotactic Conv + SwiGLU/SiLU FFN)
   with dual heads (Head 1: inline ``-``/``–``/`` ``/`` Z``; Head 2: ``  \\n`` clause & sandhi-revert).
3. Export & Eval Stage: Exports ``hyphenator_slp1.onnx`` + ``hyphenator_slp1_int8.onnx`` (~8 MB),
   verifies both via ``onnxruntime`` on held-out passages and ``hyphenations.toml``, and writes
   ``distill_eval_report.json``.
"""
from __future__ import annotations

import os as _early_os
_early_os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse
import gc
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

SLP1_CHARS = (
  "aAiIuUfFxXeEoOMH"
  "kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzshL|"
  "Z'~0123456789"
  " -–।॥,;.?!\"()>"
)
CHAR_TO_ID = {ch: idx + 2 for idx, ch in enumerate(SLP1_CHARS)}
VOCAB_SIZE = len(SLP1_CHARS) + 2
NUM_SEP_CLASSES = 5
NUM_CLAUSE_CLASSES = 7
_SHORT_V = frozenset("aiufx")
_MERGED_V = frozenset("AIUFXeEoO")
_ALL_V = _SHORT_V | _MERGED_V
_HALANT_OK = frozenset("myvrsSzdcjgbRntkpl")


def ensure_deps():
  needed = []
  for mod_name, pip_name in (
    ("indic_transliteration", "indic-transliteration"),
    ("onnx", "onnx"),
    ("onnxscript", "onnxscript"),
    ("onnxruntime", "onnxruntime"),
    ("bitsandbytes", "bitsandbytes"),
    ("peft", "peft"),
    ("accelerate", "accelerate"),
  ):
    try:
      __import__(mod_name)
    except ImportError:
      needed.append(pip_name)
  if needed:
    print(f"[setup] Installing {needed}...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", *needed])


def phon_cat(ch: str) -> int:
  if ch in _SHORT_V:
    return 1
  if ch in _MERGED_V:
    return 2
  if ch in ("M", "H"):
    return 3
  if ch in "yrlvL":
    return 4
  if ch in "NYRnm":
    return 5
  if ch in "Szsh":
    return 6
  if ch in "kKgGcCjJwWqQtTdDpPbB":
    return 7
  if ch in ("Z", "'"):
    return 8
  if ch in " -–।॥,;.?!\"()>":
    return 9
  return 0


def locate_inputs() -> tuple[Path, Path | None]:
  data_dir, lora_dir = None, None
  for root in ("/kaggle/input", "."):
    if not os.path.isdir(root):
      continue
    for dp, _, fns in os.walk(root):
      if "train_slp1.jsonl" in fns and data_dir is None:
        data_dir = Path(dp)
      if "adapter_config.json" in fns and lora_dir is None:
        lora_dir = Path(dp)
  if data_dir is None:
    raise FileNotFoundError("train_slp1.jsonl not found under /kaggle/input")
  return data_dir, lora_dir


def sandhi_skeleton(dev_txt: str, sanscript_mod) -> str:
  slp = sanscript_mod.transliterate(dev_txt, sanscript_mod.DEVANAGARI, sanscript_mod.SLP1)
  slp = re.sub(r"[\s\-–—।॥,;.?!\"'()0-9०-९]+", "", slp)
  slp = slp.replace("M", "m").replace("N", "m").replace("Y", "n").replace("R", "n")
  slp = re.sub(r"[sSzH]", "s", slp)
  slp = re.sub(r"[tdc]", "t", slp)
  return slp


def encode_teacher_pseudo(dev_pred: str, rng: random.Random, sanscript_mod) -> dict | None:
  slp = sanscript_mod.transliterate(dev_pred.strip(), sanscript_mod.DEVANAGARI, sanscript_mod.SLP1)
  slp = re.sub(r"[ \t]*\n[ \t]*", "\n", slp)
  slp = re.sub(r"[ \t]{2,}", " ", slp)
  has_cl = int("\n" in slp)
  raw_c, sep_y, cl_y = [], [], []
  i, n = 0, len(slp)
  while i < n:
    ch = slp[i]
    if ch == "\n" and raw_c:
      cl_y[-1] = 1
      if raw_c[-1] not in (" ",) and i + 1 < n and raw_c[-1] not in _HALANT_OK:
        raw_c.append(" ")
        sep_y.append(0)
        cl_y.append(0)
      elif raw_c[-1] in _HALANT_OK and i + 1 < n:
        sep_y[-1] = 3
      i += 1
      continue
    if ch in ("-", "–") and raw_c:
      sep_y[-1] = 1 if ch == "-" else 2
      i += 1
      continue
    if ch == " " and raw_c and i + 1 < n:
      prev, nxt = raw_c[-1], slp[i + 1]
      if (nxt == "Z" or prev in _HALANT_OK) and rng.random() < 0.90:
        sep_y[-1] = 3
        i += 1
        continue
    raw_c.append(ch)
    sep_y.append(0)
    cl_y.append(0)
    i += 1
  if not (8 <= len(raw_c) <= 510):
    return None
  return {"slp": "".join(raw_c), "sep": sep_y, "clause": cl_y, "has_clause": has_cl}


def run_teacher_distillation(
  uncurated_path: Path,
  lora_dir: Path | None,
  base_model: str,
  limit: int,
  torch,
  sanscript_mod,
  rng: random.Random,
) -> tuple[list[dict], dict]:
  if not uncurated_path.is_file() or lora_dir is None or limit <= 0:
    print("[teacher] Skipping teacher stage (no uncurated file or LoRA adapter).", flush=True)
    return [], {"ran": False, "accepted": 0, "total": 0}

  from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
  from peft import PeftModel

  t0 = time.time()
  raw_items = [json.loads(l)["text"] for l in open(uncurated_path, encoding="utf-8") if l.strip()][:limit]
  print(f"[teacher] Distilling {len(raw_items)} uncurated passages with {base_model} + {lora_dir}...", flush=True)

  tok = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
  if tok.pad_token_id is None:
    tok.pad_token = tok.eos_token
  tok.padding_side = "left"
  bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16
  )
  n_gpus = torch.cuda.device_count()
  base = AutoModelForCausalLM.from_pretrained(
    base_model, quantization_config=bnb_cfg, dtype=torch.float16, device_map="auto",
    max_memory={0: "13GiB", 1: "14GiB"} if n_gpus >= 2 else None, attn_implementation="sdpa", trust_remote_code=True,
  )
  teacher = PeftModel.from_pretrained(base, str(lora_dir))
  teacher.eval()
  first_dev = next(teacher.parameters()).device
  eos_ids = sorted({t for t in (tok.eos_token_id, tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")) if isinstance(t, int) and t >= 0})

  sys_p = (
    "You are an expert Sanskrit proofreader, sandhi-preserving hyphenator, and Markdown formatter.\n\n"
    "### Sanskrit Separation & Hyphenation Rules\n"
    "1. Within a line, never revert sandhi; keep dīrgha/guṇa/vṛddhi mergers joined inline (`धर्मार्थ`, `स्वप्रकाशाद्वितीय`, `महोत्सव`, `सदैव`).\n"
    "2. Split separable boundaries: yaṇ (`इत्य् एवम्`, `मध्व्-अरिः`), visarga (`रामो ऽस्ति`, `नमस् ते`), final `म्` before vowel (`फलम् अश्नुते`), assimilation (`तद् धि`, `जगत्-कारणम्`), plain samāsa (`-`, and `–` at nested upapada seams).\n"
    "3. Do NOT alter source characters or emit `[[OLD|NEW]]`; output ONLY the hyphenated text."
  )

  distilled: list[dict] = []
  accepted = 0
  bs = 12
  for st in range(0, len(raw_items), bs):
    batch_txt = raw_items[st:st + bs]
    prompts = [
      tok.apply_chat_template([{"role": "system", "content": sys_p}, {"role": "user", "content": x}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
      for x in batch_txt
    ]
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False)
    inp_len = enc["input_ids"].shape[1]
    dyn_max = min(280, max(64, int(inp_len * 0.85)))
    inputs = {k: v.to(first_dev) for k, v in enc.items()}
    with torch.no_grad(), torch.amp.autocast("cuda", dtype=torch.float16):
      gen = teacher.generate(**inputs, max_new_tokens=dyn_max, do_sample=False, temperature=None, top_p=None, top_k=None, pad_token_id=tok.pad_token_id, eos_token_id=eos_ids)
    for src_t, row in zip(batch_txt, gen):
      dec = tok.decode(row[inp_len:], skip_special_tokens=False)
      for stop_s in ("<|im_end|>", "<|endoftext|>", "<|im_start|>"):
        if stop_s in dec:
          dec = dec.split(stop_s, 1)[0]
      pred = dec.strip()
      if "[[" in pred or "<" in pred or not pred:
        continue
      if sandhi_skeleton(src_t, sanscript_mod) == sandhi_skeleton(pred, sanscript_mod):
        accepted += 1
        for _ in range(2):  # 2x weight for verified teacher pseudo-labels
          rec = encode_teacher_pseudo(pred, rng, sanscript_mod)
          if rec is not None:
            distilled.append(rec)
    if (st // bs) % 10 == 0:
      print(f"[teacher] {min(len(raw_items), st + bs)}/{len(raw_items)} processed (accepted={accepted})", flush=True)

  elapsed = round(time.time() - t0, 1)
  print(f"[teacher] Done in {elapsed}s: accepted {accepted}/{len(raw_items)} ({len(distilled)} augmented sequences). Freeing VRAM...", flush=True)
  del teacher, base, tok
  gc.collect()
  torch.cuda.empty_cache()
  return distilled, {"ran": True, "total": len(raw_items), "accepted": accepted, "distilled_sequences": len(distilled), "elapsed_sec": elapsed}


def build_conformer_student(torch):
  import torch.nn as nn
  import torch.nn.functional as F

  class ConformerBlock(nn.Module):
    def __init__(self, d_model: int = 256, n_heads: int = 8, d_ff: int = 1024, conv_k: int = 7, dropout: float = 0.1):
      super().__init__()
      self.n_heads = n_heads
      self.d_head = d_model // n_heads
      self.norm_attn = nn.LayerNorm(d_model)
      self.qkv = nn.Linear(d_model, 3 * d_model)
      self.out_proj = nn.Linear(d_model, d_model)
      self.drop = nn.Dropout(dropout)

      self.norm_conv = nn.LayerNorm(d_model)
      self.pw1 = nn.Linear(d_model, 2 * d_model)
      self.dw_conv = nn.Conv1d(d_model, d_model, kernel_size=conv_k, padding=conv_k // 2, groups=d_model)
      self.conv_norm = nn.LayerNorm(d_model)
      self.pw2 = nn.Linear(d_model, d_model)

      self.norm_ff = nn.LayerNorm(d_model)
      self.ff1 = nn.Linear(d_model, d_ff)
      self.ff2 = nn.Linear(d_ff, d_model)

    def forward(self, x, pad_mask_float):
      # 1. Bidirectional Multi-Head Attention (pure MatMul/Softmax for clean ONNX opset 17)
      b, t, d = x.shape
      h = self.norm_attn(x)
      qkv = self.qkv(h).view(b, t, 3, self.n_heads, self.d_head).permute(2, 0, 3, 1, 4)
      q, k, v = qkv[0], qkv[1], qkv[2]
      scores = torch.matmul(q, k.transpose(-2, -1)) * (1.0 / math.sqrt(self.d_head))
      scores = scores + pad_mask_float
      attn = torch.softmax(scores, dim=-1)
      ctx = torch.matmul(attn, v).transpose(1, 2).contiguous().view(b, t, d)
      x = x + self.drop(self.out_proj(ctx))

      # 2. Local 7-gram Phonotactic Depthwise Conv with GLU
      hc = self.pw1(self.norm_conv(x))
      a_g, b_g = hc.chunk(2, dim=-1)
      hc = a_g * torch.sigmoid(b_g)
      hc = self.dw_conv(hc.transpose(1, 2)).transpose(1, 2)
      hc = F.silu(self.conv_norm(hc))
      x = x + self.drop(self.pw2(hc))

      # 3. Positionwise FFN
      hf = self.ff2(self.drop(F.silu(self.ff1(self.norm_ff(x)))))
      return x + self.drop(hf)

  class Slp1ConformerTagger(nn.Module):
    def __init__(self, d_model: int = 256, n_layers: int = 8, n_heads: int = 8, max_len: int = 516):
      super().__init__()
      self.char_emb = nn.Embedding(VOCAB_SIZE, d_model, padding_idx=0)
      self.cat_emb = nn.Embedding(12, d_model)
      self.pos_emb = nn.Embedding(max_len, d_model)
      self.in_drop = nn.Dropout(0.1)
      self.layers = nn.ModuleList([ConformerBlock(d_model=d_model, n_heads=n_heads) for _ in range(n_layers)])
      self.final_norm = nn.LayerNorm(d_model)
      self.sep_head = nn.Linear(d_model, NUM_SEP_CLASSES)
      self.clause_head = nn.Linear(d_model, NUM_CLAUSE_CLASSES)

    def forward(self, char_ids, phon_cats):
      b, t = char_ids.shape
      pos = torch.arange(t, device=char_ids.device).unsqueeze(0).expand(b, t)
      x = self.in_drop(self.char_emb(char_ids) + self.cat_emb(phon_cats) + self.pos_emb(pos))
      # Float additive mask: 0.0 for valid tokens, -1e4 for PAD (char_ids == 0)
      is_pad = (char_ids == 0).to(x.dtype) * -10000.0
      pad_mask_float = is_pad.unsqueeze(1).unsqueeze(2)
      for blk in self.layers:
        x = blk(x, pad_mask_float)
      x = self.final_norm(x)
      return self.sep_head(x), self.clause_head(x)

  return Slp1ConformerTagger()


def train_student_model(student, train_recs: list[dict], eval_recs: list[dict], args, torch, rng: random.Random) -> list[dict]:
  import torch.nn as nn
  import torch.nn.functional as F

  def _enc(r: dict):
    s = r["slp"][:512]
    L = len(s)
    sup_cl = bool(r.get("has_clause", 0)) or (L < 72 and "।" in s)
    return [CHAR_TO_ID.get(c, 1) for c in s], [phon_cat(c) for c in s], r["sep"][:L], (r["clause"][:L] if sup_cl else [-100] * L)

  encoded_train, encoded_eval = [_enc(r) for r in train_recs], [_enc(r) for r in eval_recs]

  def _collate(batch):
    m_len = min(512, ((max(len(x[0]) for x in batch) + 7) // 8) * 8)
    ci, pc, sy, cy = [], [], [], []
    for c_i, p_c, s_t, c_t in batch:
      pad = m_len - len(c_i)
      ci.append(c_i + [0] * pad)
      pc.append(p_c + [0] * pad)
      sy.append(s_t + [-100] * pad)
      cy.append(c_t + [-100] * pad)
    return tuple(torch.tensor(a, dtype=torch.long) for a in (ci, pc, sy, cy))

  dev = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
  student = student.to(dev)
  net = nn.DataParallel(student) if torch.cuda.device_count() >= 2 else student
  sep_w = torch.tensor([1.0, 2.0, 3.5, 2.0, 4.5], device=dev)
  cl_w = torch.tensor([1.0, 2.5, 4.0, 4.0, 4.0, 4.0, 4.0], device=dev)
  opt = torch.optim.AdamW(student.parameters(), lr=args.lr, weight_decay=0.01)
  tot_steps = math.ceil(len(encoded_train) / args.batch_size) * args.epochs
  sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(1, tot_steps), pct_start=0.08)
  scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())

  history, best_f1, best_state = [], -1.0, None
  for ep in range(1, args.epochs + 1):
    ep_t0, ep_loss = time.time(), 0.0
    net.train()
    rng.shuffle(encoded_train)
    for w in range(0, len(encoded_train), args.batch_size * 8):
      encoded_train[w:w + args.batch_size * 8] = sorted(encoded_train[w:w + args.batch_size * 8], key=lambda z: len(z[0]))
    chunks = [encoded_train[k:k + args.batch_size] for k in range(0, len(encoded_train), args.batch_size)]
    rng.shuffle(chunks)
    for b_items in chunks:
      ci, pc, sy, cy = [t.to(dev, non_blocking=True) for t in _collate(b_items)]
      opt.zero_grad(set_to_none=True)
      with torch.amp.autocast("cuda", dtype=torch.float16, enabled=torch.cuda.is_available()):
        s_log, c_log = net(ci, pc)
        loss_s = F.cross_entropy(s_log.view(-1, NUM_SEP_CLASSES), sy.view(-1), weight=sep_w, ignore_index=-100)
        loss_c = F.cross_entropy(c_log.view(-1, NUM_CLAUSE_CLASSES), cy.view(-1), weight=cl_w, ignore_index=-100) if (cy != -100).any() else (loss_s * 0.0)
        loss = loss_s + 0.65 * loss_c
      scaler.scale(loss).backward()
      scaler.unscale_(opt)
      torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
      scaler.step(opt)
      scaler.update()
      sched.step()
      ep_loss += float(loss.item())

    net.eval()
    tp, fp_c, fn_c = 0, 0, 0
    with torch.no_grad():
      for k in range(0, len(encoded_eval), args.batch_size):
        ci, pc, sy, _ = [t.to(dev) for t in _collate(encoded_eval[k:k + args.batch_size])]
        s_pred = net(ci, pc)[0].argmax(dim=-1)
        valid = sy != -100
        g, p = sy[valid], s_pred[valid]
        tp += int(((p > 0) & (p == g)).sum().item())
        fp_c += int(((p > 0) & (p != g)).sum().item())
        fn_c += int(((p == 0) & (g > 0)).sum().item())
    prec, rec = tp / max(1, tp + fp_c), tp / max(1, tp + fn_c)
    f1 = 2 * prec * rec / max(1e-8, prec + rec)
    row = {"epoch": ep, "loss": round(ep_loss / max(1, len(chunks)), 4), "sep_prec": round(prec, 4), "sep_rec": round(rec, 4), "sep_exact_f1": round(f1, 4), "sec": round(time.time() - ep_t0, 1)}
    history.append(row)
    print(f"[epoch {ep:02d}/{args.epochs:02d}] loss={row['loss']:.4f} P={prec:.4f} R={rec:.4f} F1={f1:.4f} ({row['sec']}s)", flush=True)
    if f1 > best_f1:
      best_f1, best_state = f1, {k: v.detach().cpu().clone() for k, v in student.state_dict().items()}

  if best_state is not None:
    student.load_state_dict(best_state)
  return history


def export_and_benchmark_onnx(student, hyp_toml_path: Path, out_model_dir: Path, torch, sanscript_mod) -> dict:
  import numpy as np
  import onnxruntime as ort
  from onnxruntime.quantization import QuantType, quantize_dynamic

  out_model_dir.mkdir(parents=True, exist_ok=True)
  student_cpu = student.eval().cpu()
  dummy = (torch.ones((1, 32), dtype=torch.long), torch.ones((1, 32), dtype=torch.long))
  fp32_onnx, int8_onnx = out_model_dir / "hyphenator_slp1.onnx", out_model_dir / "hyphenator_slp1_int8.onnx"
  dyn_ax = {k: {0: "batch", 1: "seq"} for k in ("char_ids", "phon_cats", "sep_logits", "clause_logits")}
  exp_kw = dict(input_names=["char_ids", "phon_cats"], output_names=["sep_logits", "clause_logits"], dynamic_axes=dyn_ax, opset_version=17)
  try:
    torch.onnx.export(student_cpu, dummy, str(fp32_onnx), dynamo=False, **exp_kw)
  except TypeError:
    torch.onnx.export(student_cpu, dummy, str(fp32_onnx), **exp_kw)
  quantize_dynamic(str(fp32_onnx), str(int8_onnx), weight_type=QuantType.QUInt8)
  (out_model_dir / "config.json").write_text(json.dumps({"slp1_chars": SLP1_CHARS, "vocab_size": VOCAB_SIZE, "d_model": 256, "n_layers": 8}, indent=2), encoding="utf-8")

  results = {"fp32_size_mb": round(fp32_onnx.stat().st_size / (1024 ** 2), 2), "int8_size_mb": round(int8_onnx.stat().st_size / (1024 ** 2), 2)}
  if not hyp_toml_path.is_file():
    return results
  hyp_cfg = tomllib.loads(hyp_toml_path.read_text(encoding="utf-8"))

  for tag, mpath in (("fp32_onnx", fp32_onnx), ("int8_onnx", int8_onnx)):
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    sess = ort.InferenceSession(str(mpath), sess_options=opts, providers=["CPUExecutionProvider"])

    def _run_sent(txt: str) -> str:
      spans = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[\u0900-\u0963\u0966-\u097f\-–—]+", txt) if re.search(r"[\u0905-\u0939]", m.group(0))]
      if not spans:
        return txt
      slp_parts, meta, cur_pos = [], [], 0
      for idx_s, (_, _, tok) in enumerate(spans):
        if idx_s > 0:
          slp_parts.append(" ")
          cur_pos += 1
        st = sanscript_mod.transliterate(tok, sanscript_mod.DEVANAGARI, sanscript_mod.SLP1)
        slp_parts.append(st)
        meta.append((cur_pos, cur_pos + len(st), st, any(x in tok for x in ("-", "–", "—"))))
        cur_pos += len(st)
      full_s = "".join(slp_parts)
      s_all = sess.run(None, {"char_ids": np.asarray([[CHAR_TO_ID.get(c, 1) for c in full_s]], dtype=np.int64), "phon_cats": np.asarray([[phon_cat(c) for c in full_s]], dtype=np.int64)})[0][0].argmax(axis=-1).tolist()
      buf, last_e = [], 0
      for (cs, ce, orig_t), (ms, me, st, alr) in zip(spans, meta):
        buf.append(txt[last_e:cs])
        if alr or len(st) < 3:
          buf.append(orig_t)
        else:
          out_p, cur = [], []
          for ic, ch in enumerate(st):
            cur.append(ch)
            sc = s_all[ms + ic]
            if ic < len(st) - 1 and sc != 0 and any(v in _ALL_V for v in st[:ic + 1]) and any(v in _ALL_V for v in st[ic + 1:]):
              out_p.append(sanscript_mod.transliterate("".join(cur), sanscript_mod.SLP1, sanscript_mod.DEVANAGARI))
              if sc == 4 and ch in ("o", "e") and st[ic + 1] == "r":
                out_p.append(" ")
                cur = ["Z"]
                continue
              out_p.append({1: "-", 2: "–", 3: " "}.get(sc, ""))
              cur = []
          if cur:
            out_p.append(sanscript_mod.transliterate("".join(cur), sanscript_mod.SLP1, sanscript_mod.DEVANAGARI))
          buf.append("".join(out_p))
        last_e = ce
      buf.append(txt[last_e:])
      return "".join(buf)

    passed, total, diffs = 0, 0, []
    for sec in ("non_separable_mergers", "yan_sandhi", "visarga_sandhi", "final_m_sandhi", "consonant_assimilation", "samasa_and_inflected_words", "bad_split_regressions", "avagraha"):
      for c in hyp_cfg.get(sec, {}).get("cases", []):
        total += 1
        pred = _run_sent(c["input"])
        passed += int(pred == c["expected"])
        if pred != c["expected"] and len(diffs) < 12:
          diffs.append({"sec": sec, "in": c["input"], "exp": c["expected"], "pred": pred})
    for t_idem in hyp_cfg.get("idempotence", {}).get("texts", []):
      total += 1
      passed += int(_run_sent(t_idem) == t_idem)
    for rc in hyp_cfg.get("reference_sentences", {}).get("cases", []):
      total += 1
      pred = _run_sent(rc["text"])
      ok = (pred == rc["expected"]) if rc.get("mode") == "exact" else ([x for x in re.split(r"[ \-\u2013\u2014]+", pred) if x] == [x for x in re.split(r"[ \-\u2013\u2014]+", rc["expected"]) if x])
      passed += int(ok)
      if not ok:
        diffs.append({"sec": "reference", "name": rc["name"], "pred": pred[:180]})
    t_lat = time.time()
    for _ in range(30):
      _run_sent("एतदुक्तं भवति – परस्यैव ब्रह्मणो निखिलहेयप्रत्यनीकानन्तज्ञानानन्दैकस्वरूपतया सकलेतरविलक्षणस्य सन्ति।")
    results[tag] = {"passed": passed, "total": total, "pass_rate": round(passed / max(1, total), 4), "ms_per_sentence_2threads": round((time.time() - t_lat) * 1000.0 / 30.0, 2), "sample_diffs": diffs}
  return results


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--teacher-base", default="Qwen/Qwen3-14B")
  ap.add_argument("--teacher-limit", type=int, default=750)
  ap.add_argument("--epochs", type=int, default=16)
  ap.add_argument("--batch-size", type=int, default=96)
  ap.add_argument("--lr", type=float, default=8e-4)
  ap.add_argument("--out-dir", default="/kaggle/working/model")
  ap.add_argument("--seed", type=int, default=42)
  args = ap.parse_args()

  t0 = time.time()
  ensure_deps()
  import torch
  from indic_transliteration import sanscript

  rng = random.Random(args.seed)
  torch.manual_seed(args.seed)
  data_dir, lora_dir = locate_inputs()

  train_recs = [json.loads(l) for l in open(data_dir / "train_slp1.jsonl", encoding="utf-8") if l.strip()]
  eval_recs = [json.loads(l) for l in open(data_dir / "eval_slp1.jsonl", encoding="utf-8") if l.strip()]
  print(f"[data] Loaded {len(train_recs)} curated train + {len(eval_recs)} eval SLP1 sequences.", flush=True)

  distilled_recs, teacher_meta = run_teacher_distillation(
    data_dir / "uncurated_for_teacher.jsonl", lora_dir, args.teacher_base, args.teacher_limit, torch, sanscript, rng
  )
  all_train = train_recs + distilled_recs
  print(f"[student] Training 8-layer SLP1 Conformer-Transformer on {len(all_train)} total sequences...", flush=True)

  student = build_conformer_student(torch)
  n_params = sum(p.numel() for p in student.parameters())
  print(f"[student] Parameters: {n_params:,} (~{n_params * 4 / (1024 ** 2):.1f} MB FP32)", flush=True)

  history = train_student_model(student, all_train, eval_recs, args, torch, rng)
  onnx_bench = export_and_benchmark_onnx(student, data_dir / "hyphenations.toml", Path(args.out_dir), torch, sanscript)

  report = {
    "student_params": n_params,
    "curated_train_count": len(train_recs),
    "teacher_distillation": teacher_meta,
    "epoch_history_tail": history[-5:],
    "onnx_benchmark": onnx_bench,
    "elapsed_min": round((time.time() - t0) / 60.0, 2),
  }
  report_fp = Path(args.out_dir).parent / "distill_eval_report.json"
  report_fp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
  print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
  main()
