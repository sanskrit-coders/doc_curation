"""Shared Ṛk and Yajuḥ deduplication between VS-M (Mādhyandina) and VS-K (Kāṇva)."""

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  VSK_SARVA_DIR,
  VSM_RK_DIR,
  VSM_SARVA_DIR,
  VSM_YAJUH_DIR,
  chapter_distance,
  is_no_patha_bheda,
  normalize_phonetic,
  strip_trailing_refs,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.pipeline import (
  refresh_all_prefills,
  run_full_vsk_vsm_dedup,
  validate_dedup_integrity,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.rk_merger import (
  load_rk_index,
  match_and_rewrite_vsk_sections,
  merge_kanva_into_rk_tiikaa,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import (
  VskSubBlock,
  merge_vsk_hemistich_pair,
  parse_vsk_section,
  render_vsk_section,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  merge_author_bodies,
  merge_sarva_tikaa_chunks,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.yajuh_merger import (
  extract_and_link_shared_yajuh,
)

__all__ = [
  "VSK_SARVA_DIR",
  "VSM_RK_DIR",
  "VSM_SARVA_DIR",
  "VSM_YAJUH_DIR",
  "VskSubBlock",
  "chapter_distance",
  "extract_and_link_shared_yajuh",
  "is_no_patha_bheda",
  "load_rk_index",
  "match_and_rewrite_vsk_sections",
  "merge_author_bodies",
  "merge_kanva_into_rk_tiikaa",
  "merge_sarva_tikaa_chunks",
  "merge_vsk_hemistich_pair",
  "normalize_phonetic",
  "parse_vsk_section",
  "refresh_all_prefills",
  "render_vsk_section",
  "run_full_vsk_vsm_dedup",
  "strip_trailing_refs",
  "validate_dedup_integrity",
]
