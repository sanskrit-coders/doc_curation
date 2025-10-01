import os

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.scraping.html_scraper import souper
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript


def _next_url_getter(soup, *args, **kwargs):
  next_a = soup.select_one("a > svg.ml-2").parent
  next_url = f"https://vedabase.io{next_a['href']}"
  if "/advanced-view" not in next_url:
    next_url = f"{next_url}/advanced-view"
  return next_url


def dump_all(url, dest_dir, source_script=sanscript.BENGALI, *args, **kwargs):
  def md_fixer(c):
    if source_script == sanscript.BENGALI:
      c = content_processor.transliterate(text=c, source_script=sanscript.BENGALI)
      c = sanskrit_helper.fix_anunaasikaadi(c)
      c = content_processor.remove_links(c)
    return c
  def _title_maker(soup, title_prefix):
    title_tag = soup.select_one("h1")
    title = title_tag.text
    title_tag.decompose()
    button_tags = soup.select("div.select-none")
    for button_tag in button_tags:
      soup.select_one("main").parent.append(button_tag)
    if soup.select_one("a > svg.ml-2"):
      soup.select_one("main").parent.append(soup.select_one("a > svg.ml-2").parent.parent) 
    return f'{title_prefix} {title}'
  def _dumper(url, outfile_path, title_prefix, dry_run):
    return souper.dump_text_from_element(url=url, outfile_path=outfile_path, title_maker=_title_maker, md_fixer=md_fixer, text_css_selector="main",title_prefix=title_prefix, dry_run=dry_run)
  souper.dump_series(start_url=url, out_path=dest_dir, dumper=_dumper, next_url_getter=_next_url_getter, index_format="%02d", *args, **kwargs)
  library.apply_function(dir_path=dest_dir, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  arrangement.fix_index_files(dir_path=os.path.dirname(dest_dir), overwrite=False, dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda c, *args, **kwargs: md_fixer(c=c))
  pass


if __name__ == '__main__':
  # dump_all(url="https://vedabase.io/pages/z180118051000/view", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/paramparA/shankara-digvijayaH/mAdhavIyaH/")
  pass
