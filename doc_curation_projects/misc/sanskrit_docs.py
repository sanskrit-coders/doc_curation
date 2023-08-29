from doc_curation.scraping.misc_sites import sanskrit_documents

if __name__ == '__main__':
    sanskrit_documents.markdownify_all(src_dir="/home/vvasuki/gitland/sanskrit/sanskrit-documents-dump", dest_dir="/home/vvasuki/gitland/sanskrit/raw_etexts_private/mixed/sandocs-dump-markdown")