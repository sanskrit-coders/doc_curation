"""Local ONNX Runtime inference engine for the distilled SLP1 Sanskrit hyphenator.

Loads ``doc_curation/data/models/sanskrit-hyphenator-slp1/hyphenator_slp1.onnx``
(or ``hyphenator_slp1_int8.onnx``) lazily on first call with ``intra_op_num_threads=2``
so local CPU usage stays negligible (~3–6 ms per sentence, <40 MB RAM).
"""
from __future__ import annotations

import os
from pathlib import Path

from .slp1_codec import apply_slp1_predictions_to_text, text_to_ids_and_cats

DEFAULT_LOCAL_HYPHENATOR_DIR = str(
  Path(__file__).resolve().parents[2] / "data" / "models" / "sanskrit-hyphenator-slp1"
)
_MAX_WINDOW = 512
_OVERLAP = 64

_SESSION_CACHE: dict[str, object] = {}


def resolve_onnx_model_path(model_dir: str | None = None) -> str | None:
  base = Path(
    model_dir
    or os.environ.get("DOC_CURATION_HYPHENATOR_MODEL_DIR")
    or DEFAULT_LOCAL_HYPHENATOR_DIR
  )
  for fname in ("hyphenator_slp1.onnx", "hyphenator_slp1_int8.onnx"):
    cand = base / fname
    if cand.is_file():
      return str(cand)
  return None


def is_neural_hyphenator_available(model_dir: str | None = None) -> bool:
  if os.environ.get("DOC_CURATION_HYPHENATOR_BACKEND", "").lower() == "trie":
    return False
  if resolve_onnx_model_path(model_dir) is None:
    return False
  try:
    import onnxruntime  # noqa: F401
    return True
  except ImportError:
    return False


def _get_session(onnx_path: str):
  sess = _SESSION_CACHE.get(onnx_path)
  if sess is not None:
    return sess
  import onnxruntime as ort

  opts = ort.SessionOptions()
  opts.intra_op_num_threads = 2
  opts.inter_op_num_threads = 1
  opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
  sess = ort.InferenceSession(onnx_path, sess_options=opts, providers=["CPUExecutionProvider"])
  _SESSION_CACHE[onnx_path] = sess
  return sess


def predict_slp1_tags(slp_str: str, model_dir: str | None = None) -> tuple[list[int], list[int]]:
  """Predict ``(sep_labels, clause_labels)`` across ``slp_str`` with sliding-window overlap."""
  if not slp_str:
    return [], []
  import numpy as np

  onnx_path = resolve_onnx_model_path(model_dir)
  if onnx_path is None:
    raise FileNotFoundError(f"No ONNX hyphenator model found in {model_dir or DEFAULT_LOCAL_HYPHENATOR_DIR}")
  sess = _get_session(onnx_path)

  ids, cats = text_to_ids_and_cats(slp_str)
  total = len(ids)
  if total <= _MAX_WINDOW:
    inp_ids = np.asarray([ids], dtype=np.int64)
    inp_cats = np.asarray([cats], dtype=np.int64)
    sep_logits, clause_logits = sess.run(None, {"char_ids": inp_ids, "phon_cats": inp_cats})
    return sep_logits[0].argmax(axis=-1).tolist(), clause_logits[0].argmax(axis=-1).tolist()

  sep_out = [0] * total
  clause_out = [0] * total
  step = _MAX_WINDOW - _OVERLAP
  for start in range(0, total, step):
    end = min(total, start + _MAX_WINDOW)
    inp_ids = np.asarray([ids[start:end]], dtype=np.int64)
    inp_cats = np.asarray([cats[start:end]], dtype=np.int64)
    s_log, c_log = sess.run(None, {"char_ids": inp_ids, "phon_cats": inp_cats})
    s_pred = s_log[0].argmax(axis=-1).tolist()
    c_pred = c_log[0].argmax(axis=-1).tolist()
    write_from = 0 if start == 0 else (_OVERLAP // 2)
    for k in range(write_from, end - start):
      sep_out[start + k] = s_pred[k]
      clause_out[start + k] = c_pred[k]
    if end == total:
      break
  return sep_out, clause_out


def neural_hyphene(
  text: str,
  *,
  clause_newlines: bool = False,
  model_dir: str | None = None,
) -> str:
  """Hyphenate Sanskrit / mixed Markdown text using the distilled local ONNX SLP1 model."""
  if not text:
    return text
  return apply_slp1_predictions_to_text(
    text,
    lambda s: predict_slp1_tags(s, model_dir=model_dir),
    clause_newlines=clause_newlines,
  )
