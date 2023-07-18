from doc_curation import md
from doc_curation.scraping.misc_sites.brill import get_devanaagarii_page_md, fix_footnote_refs, get_footnote_def_md
from doc_curation.md.content_processor import details_helper, footnote_helper

import logging, warnings


def get_two_page_md(two_page_div):
  page_divs = list(two_page_div.select_one("table").select("td"))
  if len(page_divs) != 2:
    logging.warning(f"Got {len(page_divs)}!")

  if len(page_divs) == 1:
    comment_pages = page_divs
    core_page = None
  else:
    core_page = page_divs[0]
    # There could be tables within tables, which we don't want to select as a comment page.
    comment_pages = [page_divs[1]]
  
  final_md = ""
  comment_md = ""
  for comment_page in comment_pages:
    fix_footnote_refs(comment_page)
    md_content = md.get_md_with_pandoc(content_in=str(comment_page))
    logging.debug(f"Text snippet  : {md_content[:30]}")
    comment_md = f"{md_content}\n\n{comment_md}".strip()

  comment_detail = details_helper.Detail(title="Broo", content=comment_md)
  core_md = get_devanaagarii_page_md(core_page, comment_detail=comment_detail)
  footnote_def_md = get_footnote_def_md(two_page_div)

  final_md = f"{core_md}\n\n{footnote_def_md}"
  final_md = footnote_helper.define_footnotes_near_use(final_md)
  return final_md


