import json
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
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaaratam/kumbhakonam.json")
    if text_id == "BORI":
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaaratam/bori.json")
    elif text_id == "KK":
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaaratam/kumbhakonam.json")
    elif text_id == "SV":
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "mahaabhaaratam/vAvilla.json")

    for book_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        book_index = "%02d" % book_index
        chapter_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[book_index])

        for chapter_index in chapter_list:
            infile_path = "http://mahabharata.manipal.edu/anu-projects/MAHE/apiphpv5/readMaha2.php?src=%s&parva=%s&adh=%03d" % (text_id, book_index, chapter_index)
            outfile_path = os.path.join(base_dir, str(book_index), "%03d.md" % chapter_index)
            if os.path.exists(outfile_path):
                logging.warning("Skipping " + outfile_path)
                continue
            logging.info("Book %s chapter %d url: %s outpath: %s", book_index, chapter_index, infile_path, outfile_path)

            os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
            resource = urllib.request.urlopen(infile_path)
            content =  resource.read().decode("utf-8")
            chapter_lines = [line["text"] + "  \n" for line in json.loads(content)]
            if len(chapter_lines) > 0:
                with open(outfile_path, "w") as outfile:
                    outfile.writelines(chapter_lines)
            else:
                logging.error("No lines found for %s:%s-%03d", text_id, book_index, chapter_index)


if __name__ == '__main__':
    # get_text(text_id="KK", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/kumbhakonam")
    # get_text(text_id="BORI", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/bori")
    get_text(text_id="SV", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/mahAbhAratam/shAstri-vAvilla")
