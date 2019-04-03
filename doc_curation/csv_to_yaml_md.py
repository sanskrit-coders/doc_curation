import datetime
import logging
import os
import re
from indic_transliteration import sanscript
import pandas

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)


def convert(csv_in, out_dir, field_type_map, file_namer):
    df = pandas.read_csv(csv_in)
    # logging.info(df)
    for (_, row) in df.iterrows():
        out_file = os.path.join(out_dir, file_namer(row))
        logging.info("Creating {}".format(out_file))
        # logging.debug(row["विवरणम्"])
    
    
if __name__ == '__main__':
    def file_namer(row):
        # logging.debug(row['प्रारम्भः'])
        post_date = datetime.datetime.strptime(row['प्रारम्भः'], "%m/%d/%Y")
        file_name = sanscript.transliterate(row['लिङ्गम्'], sanscript.DEVANAGARI, sanscript.OPTITRANS)
        file_name = datetime.datetime.strftime(post_date, "%Y-%m-%d") + "_" + re.sub("[^a-zA-Z0-9\-_]", "_", file_name) + ".md"
        return file_name

    convert(
        csv_in="/home/vvasuki/Downloads/sva-kathAH.csv",
        out_dir="/home/vvasuki/vvasuki-git/rahashtippanyah/content/sva-kathAH",
        field_type_map={
            'लिङ्गम्': str,
            'विषयः': list,
            'पात्राणि': list,
            'प्रारम्भः': datetime.date,
            'अन्त्यदिनम्': datetime.date,
            'रस्यता': str,
            'रसः_भावः': list,
            'विवरणम्': "markdown_section"
        }, file_namer=file_namer)