"""Sanskrit text-processing subpackage (split from utils/sanskrit_helper.py).

Modules:
- :mod:`fixer` – regex-based corrections of Sanskrit text.
- :mod:`hyphenator` – local sandhi-preserving pada/samAsa hyphenator.
- :mod:`sandhi_check` – Pāṇinian and Vedic forward-sandhi round-trip verifier.
- :mod:`seeker` – analysis helpers (sentence splitting, verse detection).
"""

from doc_curation.sanskrit.fixer import accept_minor_changes, deduce_root, fix_accent_typos, fix_anunaasikaadi, fix_avagrahas, fix_bad_anunaasikas, fix_bad_visargas, fix_bad_vyanjanaantas, fix_intra_word_bolds, fix_lazy_anusvaara, fix_repha_duplication, fix_sacred_texts_transliteration, fix_yaNs, is_minor_dev_change, is_minor_roman_change, numerify_shloka_numbering, seperate_uvaacha, undo_gretil_analysis, undo_taittirIya_forms
from doc_curation.sanskrit.hyphenator import hyphen, hyphenate, hyphenate_text, hyphenate_word, hyphene
from doc_curation.sanskrit.sandhi_check import clean_deva_for_sandhi, sandhi_step, to_norm_slp, verify_mantra_sandhi, word_to_slp_options
from doc_curation.sanskrit.seeker import _approx_syllables, _is_verse_block, is_sanskrit_nagari, split_to_sentences

__all__ = ["_approx_syllables", "_is_verse_block", "accept_minor_changes", "clean_deva_for_sandhi", "deduce_root", "fix_accent_typos", "fix_anunaasikaadi", "fix_avagrahas", "fix_bad_anunaasikas", "fix_bad_visargas", "fix_bad_vyanjanaantas", "fix_intra_word_bolds", "fix_lazy_anusvaara", "fix_repha_duplication", "fix_sacred_texts_transliteration", "fix_yaNs", "hyphen", "hyphenate", "hyphenate_text", "hyphenate_word", "hyphene", "is_minor_dev_change", "is_minor_roman_change", "is_sanskrit_nagari", "numerify_shloka_numbering", "sandhi_step", "seperate_uvaacha", "split_to_sentences", "to_norm_slp", "undo_gretil_analysis", "undo_taittirIya_forms", "verify_mantra_sandhi", "word_to_slp_options"]
