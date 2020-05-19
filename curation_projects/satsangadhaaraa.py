from doc_curation.scraping import satsangadhaaraa

if __name__ == '__main__':
    satsangadhaaraa.dump_book(init_url="http://satsangdhara.net/devi/intro-devi.htm", out_path="/home/vvasuki/sanskrit/raw_etexts/purANam/devI-mahApurANam/", overwrite=False)
    