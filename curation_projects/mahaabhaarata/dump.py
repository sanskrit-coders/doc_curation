import logging
import os
import urllib.request

from doc_curation import text_data

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

def get_text(text_id, base_dir):
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaarata/kumbhakonam.json")
    if text_id == "BORI":
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaarata/bori.json")
    else:
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaarata/kumbhakonam.json")

    for book_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        book_index = "%02d" % book_index
        chapter_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[book_index])
        book_data = text_data.get_subunit_data(json_file=unit_info_file, unit_path_list=[book_index])

        for chapter_index in chapter_list:
            infile_path = "http://mahabharata.manipal.edu/browse/%s/%s/%d.txt" % (book_data["alt_title"].lower(), text_id, chapter_index)
            outfile_path = os.path.join(base_dir, str(book_index), "%03d.md" % chapter_index)
            logging.info("Book %s chapter %d url: %s outpath: %s", book_index, chapter_index, infile_path, outfile_path)
            if os.path.exists(outfile_path):
                logging.info("Skipping " + outfile_path)
                continue

            os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                resource = urllib.request.urlopen(infile_path)
                content =  resource.read().decode("utf-8")
                outfile.writelines([content])


if __name__ == '__main__':
    # get_text(text_id="KK", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/kumbhakonam")
    get_text(text_id="BORI", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/bori")
