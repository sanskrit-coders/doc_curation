# Sanskrit Vocabulary Tries & Hyphenation Benchmark Data

Located at `doc_curation/llm/proofreader/data/vocabulary/` (moved here from the former `doc_curation/data/vocabulary/sanskrit/`).

The legacy rule/DP/n-gram hyphenator modules (`segment.py`, `seps.py`, `corpus_ra.py`, `tries.py`, `validate.py`, `constants.py`) and their corpus n-gram/badsplit tries (`rAmAnujIya*.trie`) have been retired and replaced by:

1. **Distilled Local SLP1 Neural Hyphenator (`doc_curation/sanskrit/hyphenator/` & `doc_curation/llm/proofreader/distill/`):**
   - `neural_slp1.py` + `slp1_codec.py` + `lexicon.py` (loads `doc_curation/data/models/sanskrit-hyphenator-slp1/hyphenator_slp1.onnx` via `onnxruntime`). See [`../../distill/README.md`](../../distill/README.md).
2. **14B QLoRA Sanskrit Proofreader & Interleaver (`doc_curation/llm/proofreader/`):**
   - `Qwen/Qwen3-14B` LoRA adapter stored locally at `doc_curation/data/models/qwen3-14b-sanskrit-lora/`. See [`../../README.md`](../../README.md).

## Retained Files

- `{padas, nominal-stems, verb-stems, avyayas, dcs-stems}.trie` + `misc-vocab.toml`: Memory-mapped (`<2 ms`) by `doc_curation/sanskrit/hyphenator/lexicon.py` for microsecond *dīrgha/guṇa/vṛddhi* merger-veto checks, left/right sandhi member verification alongside the local SLP1 neural hyphenator, and `doc_curation.sanskrit.accent.samasa`.
- `hyphenations.toml`: 60-case regression and benchmark suite (`tests/hyphenator_test.py`).
- `rAmAnujIya-sources.toml`: Curated `विश्वास-प्रस्तुतिः` source list (744 Markdown files) used by both the 14B QLoRA SFT builder and the local SLP1 distillation dataset builder (`build_distill_data.py`).
