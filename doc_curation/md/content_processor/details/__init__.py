"""Details content-processor subpackage (split from details_helper.py).

Modules:
- :mod:`model` – :class:`Detail`.
- :mod:`common` – shared private helpers.
- :mod:`transformer` – in-place transforms of existing details.
- :mod:`maker` – creation of details from plain text.
- :mod:`seeker` – finding/reading details.
"""

from doc_curation.md.content_processor.details.common import _denumerify, _get_number, _normalize_spaces, _remap_source_matches
from doc_curation.md.content_processor.details.maker import interleave_from_file, non_detail_parts_to_detail, pattern_to_details, sections_to_details, shlokas_to_details, shlokas_to_muula_viprastuti_details, wrap_into_detail
from doc_curation.md.content_processor.details.model import Detail
from doc_curation.md.content_processor.details.seeker import count_details, dump_detail_content, extract_detail_tags_from_file, get_detail, get_detail_bunches, get_detail_content, get_details, get_neighbor_detail, get_nieghbor_detail
from doc_curation.md.content_processor.details.transformer import _rearrange_adjacent_details, add_detail_footnotes, adjascent_inserter, autonumber_details, dedetailsify, detail_content_replacer_soup, detail_remover, details_to_latex, insert_adjascent_element, insert_duplicate_adjascent, lift_details_out_of_wrapper, merge_details, merge_successive, open_attribute_fixer, rearrange_details, remove_adjascent_duplicates, restore_mUla, set_id_from_neighbor, transform_detail_tags_with_soup, transform_details_with_soup, transliterate_details

__all__ = ["Detail", "_denumerify", "_get_number", "_normalize_spaces", "_remap_source_matches", "_rearrange_adjacent_details", "add_detail_footnotes", "adjascent_inserter", "autonumber_details", "count_details", "dedetailsify", "detail_content_replacer_soup", "detail_remover", "details_to_latex", "dump_detail_content", "extract_detail_tags_from_file", "get_detail", "get_detail_bunches", "get_detail_content", "get_details", "get_neighbor_detail", "get_nieghbor_detail", "insert_adjascent_element", "insert_duplicate_adjascent", "interleave_from_file", "lift_details_out_of_wrapper", "merge_details", "merge_successive", "non_detail_parts_to_detail", "open_attribute_fixer", "pattern_to_details", "rearrange_details", "remove_adjascent_duplicates", "restore_mUla", "sections_to_details", "set_id_from_neighbor", "shlokas_to_details", "shlokas_to_muula_viprastuti_details", "transform_detail_tags_with_soup", "transform_details_with_soup", "transliterate_details", "wrap_into_detail"]
