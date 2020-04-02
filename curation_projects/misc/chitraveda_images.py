import logging

import regex

from doc_curation import google_sheets_index

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



if __name__ == "__main__":
    doc_data = google_sheets_index.ImageSheet(spreadhsheet_id="10yfI7hntiJ1NudQbFBFtQYGntiMdsjbu_9r6MYoCnCw",
                                              worksheet_name="चित्राणि", google_key = '/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json', url_column="imgurl", file_name_column="description")
    doc_data.download_all(destination_dir="/home/vvasuki/vvasuki-git/notes/mantra/images")

