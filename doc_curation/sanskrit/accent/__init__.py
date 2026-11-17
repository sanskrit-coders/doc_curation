"""Vedic accent processing, forward-sandhi verification, suggestion reconciliation, and block validation.

Modules:
- :mod:`sandhi_check` – Pāṇinian and Vedic forward-sandhi round-trip verifier.
- :mod:`reconciler` – Sandhi- and Pāṇini ``8.2.4–8.2.6``-aware ``[[OLD|NEW]]`` suggestion reconciler.
- :mod:`validator` – ``पद-पाठः (यान्त्रिकः)`` and ``विश्वास-प्रस्तुतिः`` integrity checks.
"""

from doc_curation.sanskrit.accent.reconciler import (
  PadapathaItem,
  US_SVARITA,
  US_UDATTA,
  apply_marks_to_token,
  bare_devanagari,
  format_padapatha_summary,
  has_us_accents,
  is_solid_provenance,
  parse_padapatha_items,
  reconcile_markdown_blocks,
  reconcile_vp_and_tk_texts,
  reconcile_vp_suggestions,
  sanitize_us_accents,
  syllables_with_marks,
  unwrap_stale_suggestions,
)
from doc_curation.sanskrit.accent.sandhi_check import (
  clean_deva_for_sandhi,
  sandhi_step,
  to_norm_slp,
  verify_mantra_sandhi,
  word_to_slp_options,
)
from doc_curation.sanskrit.accent.validator import (
  AccentValidationIssue,
  DEFAULT_VERIFIED_AA_HIATUSES,
  SIMPLEX_TINANTA_ALLOWLIST,
  VALID_ANUDATTA_RULE_TAGS,
  check_padapatha_header,
  find_false_post_udatta_svarita_arrows,
  find_unexplained_aa_hiatuses,
  find_unlicensed_unaccented_padas,
  find_unresolved_question_arrows,
  find_unsplit_upasarga_tinantas,
  find_virama_matra_glitches,
  find_vp_integrity_issues,
  has_post_udatta_svarita_in_mula,
  validate_accented_markdown,
  validate_padapatha_block,
  validate_paired_vp_and_tk,
)

__all__ = [
  "AccentValidationIssue",
  "DEFAULT_VERIFIED_AA_HIATUSES",
  "PadapathaItem",
  "SIMPLEX_TINANTA_ALLOWLIST",
  "US_SVARITA",
  "US_UDATTA",
  "VALID_ANUDATTA_RULE_TAGS",
  "apply_marks_to_token",
  "bare_devanagari",
  "check_padapatha_header",
  "clean_deva_for_sandhi",
  "find_false_post_udatta_svarita_arrows",
  "find_unexplained_aa_hiatuses",
  "find_unlicensed_unaccented_padas",
  "find_unresolved_question_arrows",
  "find_unsplit_upasarga_tinantas",
  "find_virama_matra_glitches",
  "find_vp_integrity_issues",
  "format_padapatha_summary",
  "has_post_udatta_svarita_in_mula",
  "has_us_accents",
  "is_solid_provenance",
  "parse_padapatha_items",
  "reconcile_markdown_blocks",
  "reconcile_vp_and_tk_texts",
  "reconcile_vp_suggestions",
  "sandhi_step",
  "sanitize_us_accents",
  "syllables_with_marks",
  "to_norm_slp",
  "unwrap_stale_suggestions",
  "validate_accented_markdown",
  "validate_padapatha_block",
  "validate_paired_vp_and_tk",
  "verify_mantra_sandhi",
  "word_to_slp_options",
]
