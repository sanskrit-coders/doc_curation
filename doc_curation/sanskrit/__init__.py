"""Sanskrit text-processing subpackage (split from utils/sanskrit_helper.py).

Modules:
- :mod:`fixer` – regex-based corrections of Sanskrit text.
- :mod:`seeker` – analysis helpers (sentence splitting, verse detection).
"""

from doc_curation.sanskrit.fixer import deduce_root, fix_accent_typos, fix_anunaasikaadi, fix_avagrahas, fix_bad_anunaasikas, fix_bad_visargas, fix_bad_vyanjanaantas, fix_intra_word_bolds, fix_lazy_anusvaara, fix_repha_duplication, fix_sacred_texts_transliteration, fix_yaNs, numerify_shloka_numbering, seperate_uvaacha, undo_gretil_analysis, undo_taittirIya_forms
from doc_curation.sanskrit.seeker import _approx_syllables, _is_verse_block, split_to_sentences

__all__ = ["_approx_syllables", "_is_verse_block", "deduce_root", "fix_accent_typos", "fix_anunaasikaadi", "fix_avagrahas", "fix_bad_anunaasikas", "fix_bad_visargas", "fix_bad_vyanjanaantas", "fix_intra_word_bolds", "fix_lazy_anusvaara", "fix_repha_duplication", "fix_sacred_texts_transliteration", "fix_yaNs", "numerify_shloka_numbering", "seperate_uvaacha", "split_to_sentences", "undo_gretil_analysis", "undo_taittirIya_forms"]
