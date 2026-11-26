# `doc_curation.llm.proofreader` — Sanskrit Proofreader, Hyphenator & Interleaver Toolkit

Unified toolkit for Sanskrit Markdown proofreading, sandhi/*samāsa* hyphenation, syntactic clause formatting, `/text_to_blocks` sense-unit splitting, zero-retyping commentary & translation interleaving, and lexicon-grounded Vedic *padapāṭha* drafting.

It combines **two complementary tiers**:

1. **Fast Local Deterministic / DP / Distilled-ONNX[^onnx] Engines (CPU-only, milliseconds, zero GPU):**
   - **Distilled SLP1 Neural + `BytesTrie` Hyphenator (`doc_curation.sanskrit.hyphenator`):** `7.95M` params (`30.4 MB` ONNX[^onnx]), `60/60` (`100%`) on `hyphenations.toml` in `~3–16 ms`/sentence — see [`distill/README.md`](distill/README.md).
   - **Sandhi-Aware Commentary Viterbi DP[^viterbi-dp] (`interleave_aligner.py`):** `99.1%` segment-to-core & `100.0%` role accuracy in `<3 ms`/segment.
   - **Bilingual Translation Monotonic DP[^monotonic-dp] (`translation_aligner.py`):** `100%` partition validity & `72.4%` span word-F1 in `~34 ms`/batch  
     *(span word-F1 is the harmonic mean of word-level precision and recall between each Sanskrit block's true and predicted English word spans — e.g., if a block's true translation is words `[10..20)` (10 words) and the aligner predicts `[10..24)` (14 words, 10 overlapping), precision is `10/14`, recall is `10/10`, and `F1 = 2×10 / (10+14) = 83.3%`)*.
   - **Quote-Safe Sense-Unit Block Splitter (`block_splitter.py`):** Deterministic daṇḍa/citation grouping + local hyphenation.
2. **Specialist `Qwen/Qwen3-14B` QLoRA[^qlora] Adapter + Deterministic Python Post-Guards (`backend.py`, `guards.py`):**
   - Adds contextual OCR typo proposals (`[[OLD|NEW]]`), discourse-aware `  \n` clause breaks with cross-newline sandhi unmerging, ambiguous semantic alignment resolution, and RAG-grounded Vedic *padapāṭha* drafting — wrapped in strict Python post-guards that prevent silent `मूलम्` edits, merger-veto violations, or malformed JSON partitions.

---

## 1. Model & Data Locations

| Artifact | Path / Identifier |
| :--- | :--- |
| **Local `Qwen3-14B` LoRA Adapter (`DEFAULT_LOCAL_ADAPTER_DIR`)** | `doc_curation/data/models/qwen3-14b-sanskrit-lora/` (`adapter_config.json`, `eval_report.json` tracked; `*.safetensors` git-ignored) |
| **Kaggle `Qwen3-14B` LoRA Dataset** | `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora` |
| **Kaggle SFT Dataset / Training Kernel / Batch Kernel** | `vishvasvasuki/sanskrit-proofreader-sft-data` · `vishvasvasuki/qwen3-14b-sanskrit-proofreader` · `vishvasvasuki/qwen3-14b-sanskrit-proofreader-infer` |
| **Local Distilled SLP1 ONNX Hyphenator** | `doc_curation/data/models/sanskrit-hyphenator-slp1/` (see [`distill/README.md`](distill/README.md)) |
| **Vocabulary Tries & Benchmark Suites** | `doc_curation/llm/proofreader/data/vocabulary/` (`{padas,nominal-stems,verb-stems,avyayas,dcs-stems}.trie`, `misc-vocab.toml`, `hyphenations.toml`, `rAmAnujIya-sources.toml`) |
| **Externalized Prompts & Rule Tables** | `doc_curation/llm/proofreader/data/{prompts,interleave_rules,translation_rules,synthetic_cases}.toml` |

---

## 2. How Good Is It Across Tasks?

Summary of held-out benchmarks (`eval_report.json`, `distill_eval_report.json`, and `tests/`):

| Task | Local Zero-LLM Engine | `Qwen3-14B` LoRA (+ Post-Guards) | Recommended Choice |
| :--- | :--- | :--- | :--- |
| **1. Sandhi & *Samāsa* Hyphenation (clean text)** | **`60/60` (`100%`)** on `hyphenations.toml` (`hyphene`, `~3–16 ms`/sentence on CPU) | `69.6%–73.9%` raw exact on isolated edge words → **`100%` merger-veto safety** after `enforce_post_guards`; **`97.0%` char similarity** on full `विश्वास-प्रस्तुतिः` prose (`+4.1%` vs zero-shot base) | **Local `hyphene`** for fast clean-text hyphenation; **`Qwen3-14B` (`proofread_text`)** when OCR cleanup & discourse clause breaks are also needed. |
| **2. OCR Typo Proposals (`[[OLD\|NEW]]`) & Cleanup** | *Not supported* (`hyphene` preserves root characters verbatim) | **`84.0%–97.0%` char similarity**; **0 silent mutations** (`wrap_silent_mutations` forces every lexical change into `[[OLD\|NEW]]`; conservative raw proposal recall on subtle 1-char confusions) | **`Qwen3-14B` (`proofread_text(..., suggest_corrections=True)`)** via tunnel or Kaggle batch. |
| **3. Intra-Sentence Clause Newlines (`  \n`)** | Lightweight syntactic breaks via `hyphene(..., clause_newlines=True)` | **`62.5%` multi-line clause rate** (`+37.5%` vs zero-shot base) & **`2/3` (`66.7%`)** multi-clause probe with clean cross-newline sandhi restoration (`निश्चिते सति  \nईक्षणादयः`) | **`Qwen3-14B` (`proofread_text(..., clause_newlines=True)`)** for publication-grade `विश्वास-प्रस्तुतिः`; local `hyphene` for quick drafts. |
| **4. Sense-Unit Block Splitting (`/text_to_blocks`)** | **`100%` `मूलम्` fidelity**, quote/citation-safe daṇḍa grouping + local `hyphene` (`<20 ms`/block) | Same deterministic `मूलम्` splitter + 14B `proofread_text` on `विश्वास-प्रस्तुतिः` | **Local `text_to_vipra_mula_blocks(..., use_local_hyphenator=True)`** by default; pass `backend=ProofreaderBackend(...)` only when OCR typo repair is needed simultaneously. |
| **5. Multi-Role Sanskrit Commentary Interleaving** | **`99.1%` segment-to-core**, **`100.0%` role**, **`93.8%` (`15/16`) exact window** (`<3 ms`/segment, 6-point verified) | **`100%` valid JSON**, **`100.0%` role**, **`93.8%` `unmatched_from` cutoff**, `84.9%` raw core (`+ refine_interleave_plan` post-guard) | **Local `interleave_source_into_markdown(..., backend=None)`** first (faster and higher exact-core accuracy on pratīka-rich *bhāṣyas*); add `ProofreaderBackend` for paraphrase-heavy lead-ins. |
| **6. Sanskrit ↔ English Translation Interleaving** | **`100%` (`30/30`) valid partition**, **`72.4%` span word-F1**, **`58.2%` ≤2-word boundary acc**, `5.90` words MAE (`~34 ms`/batch) | **`100%` valid partition**, **`94.4%` span word-F1**, **`93.2%` ≤2-word boundary acc**, **`0.77` words MAE**, **`68.8%` (`11/16`) all-boundaries-exact** (`+ refine_translation_mapping` post-guard) | **Local `translation_matcher.insert_translation_details(..., backend=None)`** for instant zero-GPU alignment; **`Qwen3-14B` (`backend=ProofreaderBackend(...)`)** for near-exact (`94.4%` word-F1) semantic alignment. |
| **7. Vedic `पद-पाठः (यान्त्रिकः)` & Svara Drafting** | Deterministic lexicon retrieval + `accent.to_US_accents` + `sandhi_check` / `validator` | **`46.5%` char similarity** vs **`18.6%` zero-shot base** (`+27.9%` gain), retrieves real *RV/TS/AV* attestations via `accent_helper.py` | **Draft assistant only:** always pair with `doc_curation.sanskrit.accent.{sandhi_check, validator, reconciler}` — never accept raw LLM svaras unchecked. |

### Key Safety Guarantees (Across All Modes)
- **`मूलम्` & Protected-Span Immutability:** `mask_protected_blocks` + `restore_protected_blocks` byte-protect `<details><summary>मूलम्</summary>`, Hugo frontmatter, fenced code, `{{< ... >}}` shortcodes, HTML comments, URLs, and existing `[[OLD|NEW]]` / `[[P...]]` markers before any LLM call.
- **Merger-Veto & Silent-Mutation Guards:** `rejoin_merger_violations` snaps back any accidental inline split across *savarṇadīrgha / guṇa / vṛddhi* vowels (`आ ई ऊ ऋ ए ऐ ओ औ`), and `wrap_silent_mutations` converts any unannounced character edit into an explicit `[[OLD|NEW]]` review token.
- **"No Retyping, Ever" Interleaving:** Neither commentary interleaving nor translation interleaving ever emits prose from the LLM — both return **0-based integer indices** (`segment → core` or `core → start_word_idx`), and Python splices the original text verbatim.
- **Human-in-the-Loop / Calling-LLM Random Spot-Checks:** Automated guards guarantee structural and lexical invariants, not semantic perfection on every unseen passage. Calling agents are instructed to sample random blocks/clusters across processed files (`git diff` hunks, early/middle/late passages, and tricky boundaries) to assess quality and redo/fix any subpar sections directly.

---

## 3. How to Invoke Each Task

Always use `~/gitland/python_venv/bin/python` — **never run 14B LLM weights on the local CPU**. Serve `Qwen3-14B` + LoRA on a Colab (`1× T4` AWQ) or Kaggle (`2× T4`) GPU instance, or run offline Kaggle batch jobs (`kaggle_runner.py`).

### Step 0: Start Remote `vLLM` Server (Only Needed When Using `ProofreaderBackend`)

On a Colab `1× T4` or Kaggle `1×/2× T4` GPU session:

```bash
pip install -q vllm
vllm serve Qwen/Qwen3-14B-AWQ \
  --dtype float16 --quantization awq \
  --enable-lora --lora-modules sanskrit-proofreader=/kaggle/input/qwen3-14b-sanskrit-proofreader-lora \
  --max-model-len 4096 \
  --speculative-config '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}' \
  --port 8000
# Expose over HTTPS tunnel, e.g.: cloudflared tunnel --url http://localhost:8000
```

Connect locally:

```python
from doc_curation.llm.proofreader import ProofreaderBackend

backend = ProofreaderBackend(
    base_url="https://<your-tunnel>.trycloudflare.com/v1",
    model_id="sanskrit-proofreader",
)
```

---

### A. Proofreading, Hyphenation & `[[OLD|NEW]]` OCR Suggestions (`proofread_text`)

```python
from doc_curation.llm.proofreader import build_system_prompt, proofread_text
from doc_curation.llm import text_chunker
from doc_curation.md import library

# 1. Single Markdown string (post-guards run automatically!)
cleaned_md = proofread_text(
    raw_markdown,
    backend=backend,
    clause_newlines=True,         # False -> single-line prose; True -> '  \n' syntactic clauses
    suggest_corrections=True,     # Emits [[OLD|NEW]] for OCR/print errors
    extra_instructions="Keep short śruti citations inline in double quotes.",
)

# 2. Whole directory via doc_curation.md.library.apply_function
prompt = build_system_prompt(clause_newlines=True, suggest_corrections=True)
library.apply_function(
    fn=text_chunker.process_text_chunks,
    dir_path="/path/to/markdown_dir",
    prompt=prompt,
    backend=backend,
)
```

---

### B. Sense-Unit `विश्वास-प्रस्तुतिः` + `मूलम्` Block Splitting (`/text_to_blocks`)

```python
from doc_curation.llm.proofreader import text_to_vipra_mula_blocks

# Fast local mode (uses distilled SLP1 ONNX hyphenator on CPU, zero GPU):
md_blocks = text_to_vipra_mula_blocks(
    bare_sanskrit_text,
    use_local_hyphenator=True,
    clause_newlines=True,
    max_chars=280,
)

# Or with remote 14B ProofreaderBackend (adds OCR [[OLD|NEW]] + LLM clause breaks):
md_blocks_llm = text_to_vipra_mula_blocks(
    bare_sanskrit_text,
    backend=backend,
    clause_newlines=True,
    suggest_corrections=True,
)
```

---

### C. Multi-Role Sanskrit Commentary Interleaving (`interleave_source_into_markdown`)

Handles `heading`, `viniyoga` (+ *kalpa* continuations), `avatarika` (including multi-ṛk *chandas* & edition notes), `tika` (including single-ṛk *chandas*), `translation`, `note`, and `viniyoga_sangraha`, enforces `sarvASh_TIkAH` vs `sarva-prastutiH` viniyoga withholding, and runs the 6-point verification checklist:

```python
from doc_curation.llm.proofreader import interleave_source_into_markdown

res = interleave_source_into_markdown(
    host_md,
    source_commentary_text,
    author_label="भट्टभास्करः",
    is_sarvash_tikah=False,
    backend=None,  # Local sandhi/pratīka Viterbi DP (99.1% core / 100% role); or pass `backend`
)
assert res["verification"]["ok"], res["verification"]
updated_md = res["markdown"]
withheld_viniyogas = res["withheld_viniyogas"]
```

---

### D. Sanskrit ↔ English Translation Interleaving (`translation_matcher`)

Aligns plain prose translation streams above `<details><summary>मूलम्</summary>` (and below `विश्वास-प्रस्तुतिः`) by word index with zero retyping:

```python
from doc_curation.llm import translation_matcher

# 1. Instant local Bilingual Monotonic DP (~34 ms/batch, zero GPU):
translation_matcher.insert_translation_details(
    dest_md_path,
    translation_md_path,
    backend=None,
    generate_fn=None,             # Defaults to local_translation_generate_fn
    translation_title="Thibaut",  # Custom <AuthorName> summary (defaults to "Translation")
    dry_run=False,
)

# 2. With 14B ProofreaderBackend (pre-indexed [0]..[W-1] + DP prior + refine_translation_mapping):
translation_matcher.insert_translation_details(
    dest_md_path,
    translation_md_path,
    backend=backend,
    translation_title="Thibaut",
    dry_run=False,
)
```

---

### E. Lexicon-Grounded Vedic `पद-पाठः (यान्त्रिकः)` Drafting (`accent_helper`)

```python
from doc_curation.llm.proofreader import PADAPATHA_ACCENT_SYSTEM_PROMPT
from doc_curation.llm.proofreader.accent_helper import (
    format_padapatha_user_prompt,
    retrieve_accent_candidates,
)

hits = retrieve_accent_candidates(mula_text)  # Queries RV, TS, AV padasvara + MW Babylon dicts
user_prompt = format_padapatha_user_prompt(
    mula_text,
    commentary_text=bhashya_text,
    translation_text=en_translation,
    lexicon_hits=hits,
)
chat = backend.new_chat(PADAPATHA_ACCENT_SYSTEM_PROMPT)
draft_padapatha_block = chat.send_text(user_prompt)
# Always verify & reconcile afterward with doc_curation.sanskrit.accent.{sandhi_check, validator, reconciler}!
```

---

### F. Offline Kaggle Batch Inference (Whole Directories Without Holding a Tunnel Open)

```python
from doc_curation.llm.proofreader.kaggle_jobs.kaggle_runner import (
    apply_downloaded_outputs,
    stage_batch_dataset,
)

# 1. Stage .md directory + job_config.json for Kaggle dataset upload
stage_batch_dataset(
    src_dir="/path/to/md_dir",
    staging_dir="/tmp/kaggle_batch_in",
    dataset_id="vishvasvasuki/sanskrit-proofread-batch-in",
    clause_newlines=True,
    suggest_corrections=True,
)
# 2. After `vishvasvasuki/qwen3-14b-sanskrit-proofreader-infer` finishes on Kaggle,
#    apply outputs with full मूलम् & merger-veto post-guards:
updated_files = apply_downloaded_outputs(
    src_dir="/path/to/md_dir",
    downloaded_out_dir="/tmp/kaggle_batch_out/out_md",
    allow_suggestions=True,
)
```

---

## 4. Package Structure & Retraining

- `backend.py` / `prompts.py` / `guards.py`: OpenAI-compatible `ProofreaderBackend`, dynamic prompt composer (`data/prompts.toml`), `मूलम्` masking, merger-veto snap-back, and `[[OLD|NEW]]` mutation wrapper.
- `block_splitter.py`: Quote-safe daṇḍa segmentation and sense-unit `विश्वास-प्रस्तुतिः` + `मूलम्` block builder.
- `interleave_aligner.py` / `interleave_helper.py`: Sandhi-aware pratīka & stem-IDF Monotonic Viterbi DP, `/commentary_translation` role classifier (`data/interleave_rules.toml`), LLM prompt enricher, `refine_interleave_plan` post-guard, and 6-point Markdown verifier.
- `translation_aligner.py`: Bilingual discourse-pivot, sūtra-number, technical-lexicon, and IAST→SLP1 stem Monotonic DP solver (`data/translation_rules.toml`) + `refine_translation_mapping` post-guard.
- `accent_helper.py`: Babylon *padasvara* RAG lookup + US-accent projection builder.
- `dataset/`: SFT JSONL extractor (`python -m doc_curation.llm.proofreader.dataset --out-dir /tmp/sft_data`) across proofreading, clause toggles, commentary interleaving, translation matching, and *padapāṭha* tasks.
- `distill/`: Dataset builder and `2× T4` knowledge-distillation + ONNX exporter for the `7.95M` local SLP1 hyphenator (see [`distill/README.md`](distill/README.md)).
- `kaggle_jobs/`: `train_qwen3_14b.py` (`2× T4` QLoRA trainer with chunked FP32 cross-entropy), `infer_batch.py`, and `kaggle_runner.py` (`save_adapter_locally`, `publish_lora_dataset`, `save_hyphenator_onnx_locally`).

---

[^onnx]: **ONNX (Open Neural Network Exchange):** A portable binary format for compiled neural-network computation graphs. Running our exported `.onnx` graph with `onnxruntime` executes fast CPU inference in C++ without loading PyTorch or requiring a GPU.
[^viterbi-dp]: **Viterbi DP (Viterbi Dynamic Programming):** Exact sequence-decoding algorithm that finds the single highest-scoring global assignment path `(segment_0 → core_i0, …, segment_M → core_iM)` combining per-segment pratīka/lexical match scores with transition costs, rather than making greedy local choices that can drift after an ambiguous sentence.
[^monotonic-dp]: **Monotonic DP (Monotonic Dynamic Programming):** Dynamic-programming optimal partitioning of an ordered sequence (English words `0..W-1`) into contiguous, non-overlapping, order-preserving spans `0 = b_0 ≤ b_1 ≤ … ≤ b_N = next_en` for Sanskrit blocks `0..N-1`, maximizing total bilingual anchor-hit and pacing scores while guaranteeing no crossed or out-of-order slices.
[^qlora]: **QLoRA (Quantized Low-Rank Adaptation):** Memory-efficient fine-tuning method that freezes the base LLM (`Qwen3-14B`) in 4-bit NormalFloat (`NF4`) precision and trains only small low-rank adapter matrices (`~120 MB`), fitting 14B-parameter training comfortably on `2× 16 GB` GPUs.
