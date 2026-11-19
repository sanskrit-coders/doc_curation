# Distilled Local SLP1 Sanskrit Neural Hyphenator

Lightweight, CPU-friendly local distillation of our Sanskrit sandhi & *samāsa* hyphenation pipeline (`7.95M` parameters, `30.4 MB` FP32 / `7.88 MB` INT8 ONNX[^onnx]), combined with `<2 ms` memory-mapped `BytesTrie` lexicon & sandhi witnesses (`doc_curation/llm/proofreader/data/vocabulary/`).

- **Training & distillation package:** `doc_curation/llm/proofreader/distill/` (`build_distill_data.py`, `train_distill_slp1.py`)
- **Runtime inference package:** `doc_curation/sanskrit/hyphenator/` (`neural_slp1.py`, `slp1_codec.py`, `lexicon.py`)
- **Local ONNX weights (`DEFAULT_LOCAL_HYPHENATOR_DIR`):** `doc_curation/data/models/sanskrit-hyphenator-slp1/` (`hyphenator_slp1.onnx`, `hyphenator_slp1_int8.onnx`, `config.json`, `distill_eval_report.json`)
- **Kaggle ONNX Dataset:** `vishvasvasuki/sanskrit-hyphenator-slp1-onnx`
- **Kaggle Training Kernel:** `vishvasvasuki/sanskrit-hyphenator-slp1-distill` (`2× Tesla T4`, ~25 min end-to-end)

For full OCR typo repair (`[[OLD|NEW]]`), LLM proofreading, commentary/translation interleaving, and Vedic *padapāṭha* drafting, see [`../README.md`](../README.md).

---

## 1. Architecture & Why Extended-SLP1

Tokenizing Devanāgarī into BPE subwords hides vowel-sandhi junctions inside opaque glyph clusters (`े`, `ो`, `ै`, `ौ`, *yaṇ* conjuncts). Instead, `slp1_codec.py` losslessly maps each Sanskrit span to **Extended-SLP1** (`vocab_size=80` characters + 10 phonetic-category embeddings: short vowels, merged *dīrgha/guṇa/vṛddhi* vowels, *anusvāra/visarga*, semivowels, nasals, sibilants, stops, *avagraha*, punctuation):

1. **8-Layer Bidirectional Conformer-Transformer (`7,948,812` params, `d_model=256`, `n_layers=8`):**
   - Depthwise convolution + multi-head self-attention (`intra_op_num_threads=2` in `onnxruntime`) predicts two heads at every SLP1 character position:
     - **5-way separator head (`sep_probs`):** `0=none`, `1="-"` (*samāsa* / *yaṇ* seam), `2="–"` (*upapada* / hierarchical compound seam), `3=" "` (*pada* space), `4=" ऽ"` (*pūrvarūpa avagraha* space).
     - **7-way clause-break & sandhi-restoration head (`clause_preds`):** `0=none`, `1="  \n"` (soft syntactic clause newline), plus cross-newline sandhi-restoration classes (*savarṇadīrgha*, *guṇa*, *yaṇ*, *visarga*).
   - Long paragraphs (`>512` SLP1 characters) are processed via overlapping `512`-char windows (`overlap=64`).
2. **Lexicon-Grounded Boundary Refinement (`slp1_codec.py` + `lexicon.py`):**
   - Memory-maps `{padas, nominal-stems, verb-stems, avyayas, dcs-stems}.trie` + `misc-vocab.toml` from `doc_curation/llm/proofreader/data/vocabulary/` in `<2 ms`.
   - Enforces the **Absolute Non-Separable Merger Veto** (*savarṇadīrgha*, *guṇa*, *vṛddhi* vowels `आ ई ऊ ऋ ए ऐ ओ औ` are never split inline), verifies left/right member stems under *yaṇ*/visarga/final-*m*/consonant assimilation, and snaps separator choice (`" "` vs `"-"`) when neural margin is ambiguous.

---

## 2. How Good Is It Across Tasks?

Evaluated on held-out curated `विश्वास-प्रस्तुतिः` prose (`distill_eval_report.json`) and the 60-case adversarial sandhi/compound regression suite (`tests/hyphenator_test.py` + `hyphenations.toml`):

| Task / Capability | Quality & Metric | Latency / Footprint | Notes & When to Use |
| :--- | :--- | :--- | :--- |
| **Full Hybrid Sandhi & Samāsa Hyphenation (`hyphene` / `neural_hyphene`)** | **`60 / 60` (`100.0%`)** on `hyphenations.toml` & `hyphenator_test.py` | **`~3–16 ms` / sentence** (`2` CPU threads, `<40 MB` RAM) | **Recommended default** for fast local hyphenation of clean Sanskrit & mixed English/Indic Markdown. |
| **Raw ONNX Neural Tagging Alone (zero lexicon)** | **`84.6%` exact separator F1** (`88.6%–89.2%` recall, `80.8%–81.2%` precision) on held-out prose; `39 / 60` (`65.0%`) raw pass on adversarial edge cases | `15.6 ms` (FP32, `30.4 MB`) / `17.5 ms` (INT8, `7.88 MB`) |Lexicon refinement in `slp1_codec.py` resolves the remaining rare *visarga*/*avagraha*/final-*m* edge cases to `60/60`. |
| **Non-Separable Vowel Merger Veto (`धर्मार्थ`, `रामेति`, `हितोपदेशः`, `दयार्द्र`, `अपीच्छा`, `स्वप्रकाशाद्वितीय`)** | **`100%` veto compliance** | `<1 ms` | Never splits across merged `आ/ई/ऊ/ए/ऐ/ओ/औ/आर्` vowels inline. |
| **Separable Sandhi (*yaṇ*, *visarga*, *avagraha*, final-*m*, consonant assimilation)** | **`100%` on regression suite** (`इत्य्-एवम्`, `मध्व्-अरिः`, `रामो ऽस्ति`, `दुष्प्रकृतेर् अस्य`, `नमस् ते`, `अर्थम् इति`, `तच् छ्रुत्वा`, `तद् धि`) | Included in `hyphene` | Distinguishes `-` (*yaṇ* & *samāsa*) vs `" "` (*pada* seam, *visarga*, final-*m*, *avagraha*). |
| **Hierarchical Compound Hyphens (`-` vs `–`)** | Preserves & predicts `–` on long *Śrībhāṣya* compounds (`सौगन्ध्य–सौकुमार्य–लावण्य-यौवनाद्य्–...`) | Included in `hyphene` | Trained strictly on 744 hyphenated `rAmAnujIya` `विश्वास-प्रस्तुतिः` files (`44,000` sequences) + `339` sandhi-verified `Qwen3-14B` teacher sequences. |
| **Syntactic Clause Line Breaks (`clause_newlines=True`)** | Good lightweight draft (`  \n` after gerunds, participial clauses, `,`, `–`, daṇḍas) | Same single ONNX pass | Useful for quick local formatting; for deeper discourse-aware clause breaks + cross-newline sandhi unmerging, use `Qwen3-14B` LoRA (`proofread_text`). |
| **Sense-Unit Block Splitting (`/text_to_blocks`)** | Deterministic quote/citation-safe daṇḍa grouping + local hyphenation via `text_to_vipra_mula_blocks(..., use_local_hyphenator=True)` | `<20 ms` / block | Preserves `मूलम्` verbatim while hyphenating `विश्वास-प्रस्तुतिः` locally. |
| **OCR Typo Detection (`[[OLD\|NEW]]`), Interleaving, Vedic Svaras** | **Not supported** by the 8M boundary tagger | — | By design, `hyphene` **never alters root consonants or vowels**. Use [`doc_curation/llm/proofreader`](../README.md) for OCR typo repair and interleaving. |

---

## 3. How to Invoke Locally

Always run with the project virtualenv (`~/gitland/python_venv/bin/python`). The ONNX session loads lazily on first call with `intra_op_num_threads=2`.

### A. Hyphenate Sanskrit or Mixed Markdown Text (`hyphene`)

```python
from doc_curation.sanskrit.hyphenator import hyphene, hyphenate_word, is_neural_hyphenator_available

assert is_neural_hyphenator_available()

# 1. Single word (idempotent)
print(hyphenate_word("इत्येवम्"))          # -> "इत्य्-एवम्"
print(hyphenate_word("स्वप्रकाशाद्वितीय"))  # -> "स्वप्रकाशाद्वितीय" (merger veto respected)

# 2. Full sentence or mixed English/Devanāgarī Markdown (+++(...)+++ glosses & `code` are protected)
text = "तत्र धर्मार्थकामानां कारणविशेषे निश्चिते सति ईक्षणादयः प्रवर्तन्ते।"
print(hyphene(text, clause_newlines=False))
# With intra-sentence syntactic clause breaks (`  \n`):
print(hyphene(text, clause_newlines=True))
```

### B. Generate `विश्वास-प्रस्तुतिः` + `मूलम्` Sense-Unit Blocks (`/text_to_blocks`)

```python
from doc_curation.llm.proofreader import text_to_vipra_mula_blocks

blocks_md = text_to_vipra_mula_blocks(
    raw_sanskrit_text,
    use_local_hyphenator=True,  # Uses distilled ONNX hyphenator locally (no GPU/LLM needed)
    clause_newlines=True,
    max_chars=280,
)
```

### C. Bulk-Process a Directory of Markdown Files

```python
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.sanskrit.hyphenator import hyphene

# Example: hyphenate only विश्वास-प्रस्तुतिः blocks while leaving मूलम् untouched
library.apply_function(
    fn=details_helper.process_details_with_keys,
    dir_path="/path/to/markdown_dir",
    keys=["विश्वास-प्रस्तुतिः"],
    processing_fn=lambda s: hyphene(s, clause_newlines=False),
)
```

### D. Environment Overrides

- `DOC_CURATION_HYPHENATOR_MODEL_DIR=/custom/dir`: Load `hyphenator_slp1.onnx` (or `hyphenator_slp1_int8.onnx`) from an alternate directory.
- `DOC_CURATION_HYPHENATOR_BACKEND=trie`: Bypass ONNX Runtime and fall back to the minimal emergency lexicon splitter (`_fallback_lexicon_split_word`).

---

## 4. Rebuilding Data & Retraining on Kaggle (Never Train Locally)

Per project compute rules, **never run neural training or 14B teacher labeling on the local CPU**.

### Step 1: Build SLP1 Distillation JSONL Locally (lightweight text scan, ~15s)

```bash
PYTHONPATH=/home/vvasuki/gitland/sanskrit-coders/doc_curation \
  ~/gitland/python_venv/bin/python -m doc_curation.llm.proofreader.distill.build_distill_data \
  --out-dir /tmp/distill_hyphenator_data \
  --max-curated 44000 \
  --max-uncurated 1200
```

*(Note: `_collect_curated_files()` intentionally harvests curated supervision exclusively from the 744 hyphenated `rAmAnujIya-sources.toml` files so unhyphenated Vedic mantra corpora cannot dilute compound-hyphen recall.)*

### Step 2: Push Distillation Kernel to Kaggle (`2× Tesla T4`)

1. Upload `/tmp/distill_hyphenator_data` to Kaggle dataset `vishvasvasuki/sanskrit-hyphenator-distill-data`.
2. Push `train_distill_slp1.py` with `distill-kernel-metadata.json` (`vishvasvasuki/sanskrit-hyphenator-slp1-distill`):
   - **Stage 1 (Isolated Child Subprocess):** Loads `Qwen/Qwen3-14B` + `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora` across `2× T4`, pseudo-labels uncurated `मूलम्` passages, verifies character-skeleton invariants, writes JSONL, and exits so the OS reclaims 100% of host & GPU memory.
   - **Stage 2 (Student Training & ONNX Export):** Pre-packs sequences into `int16` tensors (`<160 MB` RAM), trains the 8-layer Conformer-Transformer (`22` epochs, ~31s/epoch), exports opset-17 `hyphenator_slp1.onnx` (`30.4 MB`) + quantized `hyphenator_slp1_int8.onnx` (`7.88 MB`), and writes `distill_eval_report.json`.
3. Persist downloaded artifacts into `doc_curation/data/models/sanskrit-hyphenator-slp1/`:

```python
from doc_curation.llm.proofreader.kaggle_jobs.kaggle_runner import save_hyphenator_onnx_locally

save_hyphenator_onnx_locally("/path/to/downloaded_kernel_out")
```

---

[^onnx]: **ONNX (Open Neural Network Exchange):** Portable compiled neural-network graph format executed locally on CPU via `onnxruntime` without loading PyTorch or requiring a GPU.
