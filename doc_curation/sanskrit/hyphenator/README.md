# `doc_curation.sanskrit.hyphenator` — Local SLP1 Neural + Lexicon Hyphenator

Runtime inference package for the distilled local Sanskrit sandhi & *samāsa* hyphenator (`7.95M`-parameter 8-layer Extended-SLP1 Conformer-Transformer via `onnxruntime`, paired with `<2 ms` memory-mapped `BytesTrie` lexicon witnesses).

For full architecture, benchmarks (`60/60` on `hyphenations.toml`, `~3–16 ms`/sentence on 2 CPU threads), and Kaggle distillation instructions, see **[`../../llm/proofreader/distill/README.md`](../../llm/proofreader/distill/README.md)**.  
For the `Qwen3-14B` QLoRA proofreader (`[[OLD|NEW]]` OCR typo repair, commentary/translation interleaving, *padapāṭha* drafting), see **[`../../llm/proofreader/README.md`](../../llm/proofreader/README.md)**.

---

## Quick Usage

```python
from doc_curation.sanskrit.hyphenator import (
    hyphene,          # aliases: hyphen, hyphenate, hyphenate_text
    hyphenate_word,
    is_neural_hyphenator_available,
    neural_hyphene,
)

assert is_neural_hyphenator_available()

# Single word (idempotent; respects dīrgha/guṇa/vṛddhi merger vetoes)
hyphenate_word("इत्येवम्")          # -> "इत्य्-एवम्"
hyphenate_word("स्वप्रकाशाद्वितीय")  # -> "स्वप्रकाशाद्वितीय"

# Sentence or mixed English/Devanāgarī Markdown
hyphene("तत्र धर्मार्थकामानां कारणविशेषे निश्चिते सति ईक्षणादयः प्रवर्तन्ते।", clause_newlines=False)
hyphene("तत्र धर्मार्थकामानां कारणविशेषे निश्चिते सति ईक्षणादयः प्रवर्तन्ते।", clause_newlines=True)
```

## Package Layout

- `__init__.py`: Public `hyphene(...)` and `hyphenate_word(...)` entry points (with minimal lexicon fallback if ONNX weights are absent).
- `neural_slp1.py`: Lazy `onnxruntime` CPU session (`intra_op_num_threads=2`) loading `doc_curation/data/models/sanskrit-hyphenator-slp1/hyphenator_slp1.onnx` (override via `DOC_CURATION_HYPHENATOR_MODEL_DIR`).
- `slp1_codec.py`: Lossless Devanāgarī ↔ Extended-SLP1 span mapper, `+++(...)+++` / inline-code / URL / `[[...]]` masker, and lexicon-guided boundary refinement.
- `lexicon.py`: Memory-mapped `BytesTrie` loader reading `{padas, nominal-stems, verb-stems, avyayas, dcs-stems}.trie` + `misc-vocab.toml` from `doc_curation/llm/proofreader/data/vocabulary/` (also used by `doc_curation.sanskrit.accent.samasa`).
