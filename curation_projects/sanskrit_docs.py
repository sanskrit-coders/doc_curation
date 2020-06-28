from doc_curation.scraping import sanskrit_documents

if __name__ == '__main__':
    sanskrit_documents.markdownify_all(src_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sandocs-dump/sanskritdocuments.org", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sandocs-dump-markdown")