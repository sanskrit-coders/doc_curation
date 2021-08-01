from doc_curation.mail_stream import mailman



if __name__ == '__main__':
  pass
  # mailman.scrape_months(url="https://list.indology.info/pipermail/indology/", list_id="[INDOLOGY] ", dest_dir_base="/home/vvasuki/hindu-comm/mail_stream_indology/", dry_run=False)
  mailman.scrape_months(url="https://lists.advaita-vedanta.org/archives/advaita-l/", list_id="[Advaita-l] ", dest_dir_base="/home/vvasuki/hindu-comm/mail_stream_advaita-l/", dry_run=False)