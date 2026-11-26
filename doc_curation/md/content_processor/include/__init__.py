"""Includes content-processor subpackage (split from include_helper.py).

Modules:
- :mod:`model` – :class:`Include`.
- :mod:`maker` – creation of include paths, titles and migrated texts.
- :mod:`transformer` – in-place transforms of includes in content.
- :mod:`seeker` – resolving file paths from include urls.
- :mod:`fixer` – normalizing ``title``/``includeTitle``/``collapsed`` attributes and wrappers.
"""

from doc_curation.md.content_processor.include.fixer import (
  IncludeTitleChange,
  IncludeTitleFixReport,
  fix_include_titles,
  fix_include_titles_in_content,
)
from doc_curation.md.content_processor.include.maker import init_word_title_maker, make_alt_include, migrate_and_replace_texts, static_include_path_maker, vishvAsa_include_maker
from doc_curation.md.content_processor.include.model import Include
from doc_curation.md.content_processor.include.seeker import (
  BrokenInclude,
  IncludeAuditReport,
  TagBalanceIssue,
  audit_includes,
  audit_includes_in_content,
  check_tag_balance,
  diagnose_include_url,
  file_path_from_url,
  resolve_hugo_include_file_path,
  resolve_include_file_path,
)
from doc_curation.md.content_processor.include.transformer import alt_include_adder, deinclude, deinclude_content, filter_details_by_pattern, find_js_include_divs, fix_rel_urls, include_basename_fixer, include_core_with_commentaries, include_to_details, includes_to_details, old_include_remover, prefill_include, prefill_includes, surgical_prefill_content, surgical_prefill_includes, surgical_prefill_transitive, transform_include_lines, transform_includes_with_soup

__all__ = ["BrokenInclude", "Include", "IncludeAuditReport", "IncludeTitleChange", "IncludeTitleFixReport", "TagBalanceIssue", "alt_include_adder", "audit_includes", "audit_includes_in_content", "check_tag_balance", "deinclude", "deinclude_content", "diagnose_include_url", "file_path_from_url", "filter_details_by_pattern", "find_js_include_divs", "fix_include_titles", "fix_include_titles_in_content", "fix_rel_urls", "include_basename_fixer", "include_core_with_commentaries", "include_to_details", "includes_to_details", "init_word_title_maker", "make_alt_include", "migrate_and_replace_texts", "old_include_remover", "prefill_include", "prefill_includes", "resolve_hugo_include_file_path", "resolve_include_file_path", "static_include_path_maker", "surgical_prefill_content", "surgical_prefill_includes", "surgical_prefill_transitive", "transform_include_lines", "transform_includes_with_soup", "vishvAsa_include_maker"]
