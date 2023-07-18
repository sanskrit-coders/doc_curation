import os
import textwrap
import logging
from indic_transliteration import sanscript
from curation_utils import scraping
from doc_curation import md
from doc_curation.md.content_processor import details_helper, footnote_helper
from doc_curation.md.file import MdFile
from tqdm import tqdm


def dump_chapter(url, dest_path, dry_run=False, overwrite=False):
  # Example: https://brill.com/edcollchap-oa/book/9789004537651/BP000002.xml
  if os.path.exists(dest_path) and not overwrite:
    logging.info(f"Exists {dest_path}! Returning.")
    return 
  soup = scraping.get_soup(url=url)
  title = soup.select_one("h1.title").text
  two_page_divs = list(soup.select("#chapterBody div.tableWrap"))
  if len(two_page_divs) == 0:
    chapter_div = soup.select_one("#chapterBody")
    fix_footnote_refs(chapter_div)
    content = md.get_md_with_pandoc(content_in=str(chapter_div))
    content = content.replace("\[", "[").replace("\]", "]")
    footnote_def_md = get_footnote_def_md(chapter_div)
    content = content + "\n\n" + footnote_def_md
    content = footnote_helper.define_footnotes_near_use(content)
  else:
    from doc_curation.scraping.misc_sites.brill import two_page_style
    content = ""
    logging.info(f"Got {len(two_page_divs)} two page divs.")
    for two_page_div in tqdm(two_page_divs):
      page_content = two_page_style.get_two_page_md(two_page_div)
      content = f"{content}\n\n{page_content}"

  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title.strip()}, content=content, dry_run=dry_run)


def get_devanaagarii_page_md(core_page, comment_detail):
  # Replace footnote markers
  fix_footnote_refs(core_page)
  md_content = md.get_md_with_pandoc(content_in=str(core_page))

  logging.debug(f"Text snippet  : {md_content[:30]}")
  md_content = md_content.replace("\[", "[").replace("\]", "]").replace("\|", "|")
  md_content = sanscript.transliterate(md_content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI, suspend_on= set(['<', '[^']), suspend_off = set(['>', ']']))
  md_content = md_content.replace("।।", "॥")
  prastuti_detail = details_helper.Detail(title="विश्वास-प्रस्तुतिः", content=md_content)
  core_detail = details_helper.Detail(title="मूलम्", content=md_content)
  md_content = f"{prastuti_detail.to_md_html()}\n\n{comment_detail.to_md_html()}\n\n{core_detail.to_md_html()}"
  return md_content


def fix_footnote_refs(page):
  sups = page.select("a>sup")
  footnote_refs = [sup.parent for sup in sups]
  logging.info(f"Got {len(footnote_refs)} footnote refs.")
  for footnote_ref in tqdm(footnote_refs):
    id = footnote_ref["href"].replace("#", "")
    footnote_ref.insert_after(f"[^{id}]")
  for footnote_ref in footnote_refs:
    footnote_ref.decompose()


def get_footnote_def_md(base_div):
  # Footnote defs
  footnote_def_divs = base_div.select(".tableWrapFoot>div")
  if len(footnote_def_divs) == 0:
    footnote_def_divs = base_div.select(".footnoteGroup>div")
  footnote_mds = []
  logging.info(f"Got {len(footnote_def_divs)} footnote defs.")
  for footnote_def in tqdm(footnote_def_divs):
    id = footnote_def["id"]
    sup_tag = footnote_def.select_one("sup")
    if sup_tag is None:
      sup_tag = footnote_def.select_one("a")
    if sup_tag is None:
      logging.warning(f"No superscript found! {id}")
    else:
      sup_tag.decompose()
    md_content = md.get_md_with_pandoc(content_in=str(footnote_def))
    md_content = textwrap.indent(md_content, "    ")
    md_content = f"[^{id}]:\n\n{md_content}"
    footnote_mds.append(md_content)

  return "\n\n".join(footnote_mds)
