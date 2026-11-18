# Sanskrit Vocabulary Tries & Hyphenation Benchmark Data

The legacy rule/DP/n-gram hyphenator modules (`segment.py`, `seps.py`, `corpus_ra.py`, `tries.py`, `validate.py`, `constants.py`) and their corpus n-gram/badsplit tries (`rAmAnujIya*.trie`) have been retired and replaced by:

1. **Distilled Local SLP1 Neural Hyphenator (`doc_curation/sanskrit/hyphenator/`):**
   - `neural_slp1.py` + `slp1_codec.py` + `lexicon.py` (loads `doc_curation/data/models/sanskrit-hyphenator-slp1/hyphenator_slp1.onnx` via `onnxruntime`).
2. **14B QLoRA Sanskrit Proofreader & Interleaver (`doc_curation/llm/proofreader/`):**
   - `Qwen/Qwen3-14B` LoRA adapter stored locally at `doc_curation/data/models/qwen3-14b-sanskrit-lora/`.

## Retained Files

- `{padas, nominal-stems, verb-stems, avyayas, dcs-stems}.trie` + `misc-vocab.toml`: Memory-mapped (`<2 ms`) by `lexicon.py` for microsecond *dīrgha/guṇa/vṛddhi* merger-veto checks alongside the local SLP1 neural hyphenator and for `doc_curation.sanskrit.accent.samasa`.
- `hyphenations.toml`: Regression and benchmark suite (`tests/hyphenator_test.py`).
- `rAmAnujIya-sources.toml`: Curated `विश्वास-प्रस्तुतिः` source list used by SFT & distillation dataset builders.
