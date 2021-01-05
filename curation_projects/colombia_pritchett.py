from doc_curation.scraping.html import souper


def html_fixer(soup):
    souper.tag_replacer(soup=soup, css_selector="font[size*=\"+4\"]", tag_name="h1")
    souper.tag_replacer(soup=soup, css_selector="font[size*=\"+3\"]", tag_name="h2")
    souper.tag_replacer(soup=soup, css_selector="font[size*=\"+2\"]", tag_name="h3")
    souper.tag_replacer(soup=soup, css_selector="font[size*=\"+1\"]", tag_name="h4")

def title_maker(soup, title_prefix):
    if len(soup.select("h1")) > 0:
        title = souper.title_from_element(soup=soup, title_css_selector="h1", title_prefix=title_prefix)
    else:
        title = souper.title_from_element(soup=soup, title_css_selector="h2", title_prefix=title_prefix)
    return title


dumper = lambda url, outfile_path, dry_run, index: souper.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector="body", title_maker=title_maker, html_fixer=html_fixer, dry_run=dry_run)
souper.markdownify_local_htmls(src_dir="/home/vvasuki/sanskrit/raw_etexts_english/local/pritchett/00islamlinks", dest_dir="", dumper=dumper)