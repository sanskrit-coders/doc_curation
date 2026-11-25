"""VS-K (Kāṇva Śukla Yajurveda Saṃhitā) parser, repair, splitter, and bhāṣya aligner.

Reconstructs clean ``vAjasaneyam/kANvam/saMhitA/sarva-prastutiH/{01..40}.md``
matching the VS-M structure (kaṇḍikā headings, sense-unit ``विश्वास-प्रस्तुतिः``
+ ``मूलम्`` pairs, ``सर्वा अवतारिकाः`` above VP, and ``सर्वाष् टीकाः`` containing
``Griffith``, ``मूलम्``, sandhi-verified ``पदपाठः``, and native Kāṇva bhāṣyas:
Sāyaṇa Ch 1–40, Ānandabodha Ch 1–40, Anantācārya Ch 21–30), while skipping
Dayānanda Sarasvatī content.
"""
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  _ACCENTS_STR,
  _COMMENTARY_PROSE_RE,
  _DEV_ORDINALS_CH,
  _KANDIKA_40_16_HEADER_WORDS_CHECK,
  _VP_STRIP_RE,
  _VSK_40_16_MISSING_MULA,
  _VSK_40_16_MISSING_VP,
  _VSM_APPARATUS_RE,
  _VSM_HEADER_RE,
  KANVA_AVATARIKA_SPECS,
  KANVA_PDF_DIR,
  KANVA_TIKA_SPECS,
  VSK_SAMHITA_DIR,
  VSK_SARVA_PRASTUTI_DIR,
  VSM_SARVA_PRASTUTI_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.corpus import (
  build_and_write_vsk_corpus,
  collect_all_vsk_sources,
  format_vsk_coverage_block,
  hyphenate_vsk_vp_clauses,
  plan_kanva_kandika_alignment,
  render_vsk_kandika_section,
  validate_vsk_corpus,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.padapatha import (
  _carve_sub_pada,
  _clean_pada_tokens,
  _format_pada_clause,
  _looks_galita_or_short,
  _pada_tok_eff_skel,
  _subsequence_ratio,
  _verify_pada_tokens,
  reconcile_and_split_padapatha,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.prose_clean import (
  clean_raw_bhashya_text,
  clean_vsk_commentary_blocks_in_dir,
  strip_pune_margin_numbers,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.repair import (
  _convert_indike_to_vp_mula,
  _dedup_and_repair_raw_chapter,
  _norm_skel,
  build_kandika_heading,
  load_indike_by_chapter,
  load_vsk_repaired_kandikas,
  normalize_vsk_text,
  split_kandika_clauses,
  to_devanagari_ordinal,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.ssu_indike import (
  _split_multi_mantra_gloss,
  align_vsm_blocks_to_kandikas,
  build_indike_sayana_fallback,
  parse_ssu_1978_sayana,
  parse_ssu_2011_vol4,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.vsm_matcher import (
  _partition_pada_for_clauses,
  _split_griffith_across_clauses,
  build_vsm_index,
  match_vsm_clauses,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.vsm_ocr import (
  _is_mula_line,
  _is_padapatha_line,
  _ord_variants,
  _split_author_blocks_vsm,
  clean_drive_ocr_markdown,
  clean_vsm_lines,
  slice_vsm_volume_chapters,
)

__all__ = [
  "KANVA_AVATARIKA_SPECS",
  "KANVA_PDF_DIR",
  "KANVA_TIKA_SPECS",
  "VSK_SAMHITA_DIR",
  "VSK_SARVA_PRASTUTI_DIR",
  "VSM_SARVA_PRASTUTI_DIR",
  "align_vsm_blocks_to_kandikas",
  "build_and_write_vsk_corpus",
  "build_indike_sayana_fallback",
  "build_kandika_heading",
  "build_vsm_index",
  "clean_drive_ocr_markdown",
  "clean_raw_bhashya_text",
  "clean_vsk_commentary_blocks_in_dir",
  "clean_vsm_lines",
  "collect_all_vsk_sources",
  "format_vsk_coverage_block",
  "hyphenate_vsk_vp_clauses",
  "load_indike_by_chapter",
  "load_vsk_repaired_kandikas",
  "match_vsm_clauses",
  "normalize_vsk_text",
  "parse_ssu_1978_sayana",
  "parse_ssu_2011_vol4",
  "plan_kanva_kandika_alignment",
  "reconcile_and_split_padapatha",
  "render_vsk_kandika_section",
  "slice_vsm_volume_chapters",
  "split_kandika_clauses",
  "strip_pune_margin_numbers",
  "to_devanagari_ordinal",
  "validate_vsk_corpus",
]
