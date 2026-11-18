# Sanskrit Proofreader, Hyphenator & Interleaver LLM (`Qwen3-14B`)

Text-only QLoRA adapter on **`Qwen/Qwen3-14B`** (also compatible with **`Qwen/Qwen3-14B-AWQ`** on 1×T4 Colab/Kaggle and **`Qwen/Qwen3-32B-AWQ`** on 2×T4 Kaggle) covering:

1. **`proofreader-hyphenator` skill:**
   - Separable sandhi & compound splitting (`-` within samāsa, `–` at upapada seams, space at pada seams) with **absolute non-separable merger veto** (`धर्मार्थ`, `स्वप्रकाशाद्वितीय`, `महोत्सव`, `सदैव` kept whole) — including embedded Sanskrit inside English/Indic prose.
   - Inline source-error suggestions `[[OLD|NEW]]` & illegible markers `[[??]]`, page markers `[[P64]]`, footnotes `[^12_1]`, and `<details><summary>मूलम्</summary>` preservation.
   - **Instruction-conditioned formatting:** Toggle `clause_newlines=True` (separating intra-sentence syntactic phrases/clauses onto soft-broken lines `  \n`) or pass custom rules via `extra_instructions="..."`.
   - **Deterministic Python post-guards (`guards.py`):** Pre-masks `मूलम्` blocks, snaps back any accidental merger-veto violations, and wraps any silent lexical edit into `[[OLD|NEW]]`.
2. **`interleaver` skill ("no retyping, ever"):**
   - Native cursor-index alignment for `doc_curation.llm.translation_matcher` (`{"starts": ..., "skip": ..., "next_en": ...}`).
   - Multi-role commentary & translation segment-to-core JSON alignment (`interleave_helper.py`: `viniyoga`, `avatarika`, `translation`, `tika`, `note`, `viniyoga_sangraha`, `heading`), enforcing `sarvASh_TIkAH` vs `sarva-prastutiH` placement rules.
3. **`accenting` skill (lexicon-grounded `पद-पाठः (यान्त्रिकः)`):**
   - `accent_helper.py` retrieves candidate accents from `rv-padasvara-dev` / `kyv-ts-padasvara` / `av-padasvara` / `mw-cologne` + `accent.to_US_accents(मूलम्)` and produces `<details><summary>पद-पाठः (यान्त्रिकः...)</summary>` blocks for `reconciler.py` & `validator.py`.
   - Open-ended `grammar` sūtra Q&A is intentionally left to deterministic `vidyut`/`airaavata` & `aShTAdhyAyI-com-data` to keep the adapter lean (~120 MB) and hallucination-free.

---

## Local & Kaggle Identifiers

- **Local Saved LoRA Adapter (`DEFAULT_LOCAL_ADAPTER_DIR`):** `doc_curation/data/models/qwen3-14b-sanskrit-lora/` (persisted via `save_adapter_locally()`, with `*.safetensors` and `tokenizer.json` git-ignored while tracking `adapter_config.json` and `eval_report.json`)
- **Training Dataset:** `vishvasvasuki/sanskrit-proofreader-sft-data`
- **Training Kernel:** `vishvasvasuki/qwen3-14b-sanskrit-proofreader` (`2× NvidiaTeslaT4`)
- **Trained LoRA Adapter Dataset:** `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora`
- **Batch Inference Kernel:** `vishvasvasuki/qwen3-14b-sanskrit-proofreader-infer`

---

## Usage

### A. Interactive / Streaming via Colab or Kaggle Tunnel (`vLLM` + `doc_curation`)

On a Colab 1×T4 or Kaggle 1×/2×T4 notebook:

```bash
pip install -q vllm
vllm serve Qwen/Qwen3-14B-AWQ \
  --dtype float16 --quantization awq \
  --enable-lora --lora-modules sanskrit-proofreader=/path/to/adapter \
  --max-model-len 4096 \
  --speculative-config '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":4}' \
  --port 8000
# Expose with: cloudflared tunnel --url http://localhost:8000
```

Then locally in `~/gitland/python_venv/bin/python`:

```python
from doc_curation.llm.proofreader import ProofreaderBackend, build_system_prompt, proofread_text
from doc_curation.llm import text_chunker
from doc_curation.md import library

backend = ProofreaderBackend(
    base_url="https://<tunnel>.trycloudflare.com/v1",
    model_id="sanskrit-proofreader",
)

# 1. Single string (with intra-sentence clause newlines enabled!)
out = proofread_text(
    raw_markdown,
    backend=backend,
    clause_newlines=True,
    suggest_corrections=True,
    extra_instructions="Keep short quotations inline in double quotes.",
)

# 2. Whole directory via doc_curation text_chunker
prompt = build_system_prompt(clause_newlines=True, suggest_corrections=True)
library.apply_function(
    fn=text_chunker.process_text_chunks,
    dir_path="/path/to/md_dir",
    prompt=prompt,
    backend=backend,
)
```

### B. Rebuilding Dataset & Retraining on Kaggle

```bash
PYTHONPATH=/home/vvasuki/gitland/sanskrit-coders/doc_curation \
  ~/gitland/python_venv/bin/python -m doc_curation.llm.proofreader.dataset \
  --out-dir /tmp/sft_data
~/.local/bin/kaggle datasets version -p /tmp/sft_data -m "Update SFT data"
~/.local/bin/kaggle kernels push -p doc_curation/llm/proofreader/kaggle_jobs/kernel_train
```
