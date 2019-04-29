import codecs
import datetime
import logging
import os
import re

import yamldown as yamldown
from indic_transliteration import xsanscript
import pandas

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)

FIELD_TYPE_MARKDOWN_SECTION = "markdown_section"


def date_format_converter_us_to_yyyy_mm_dd(date_str):
    date_in = datetime.datetime.strptime(date_str, "%m/%d/%Y")
    return datetime.datetime.strftime(date_in, "%Y-%m-%d")

def convert(csv_in, out_dir, field_type_map, file_namer, date_format_converter=None):
    df = pandas.read_csv(csv_in)
    # logging.info(df)
    for (_, row) in df.iterrows():
        out_file = os.path.join(out_dir, file_namer(row))
        logging.info("Creating {}".format(out_file))
        # logging.debug(row["विवरणम्"])
        yml = {}
        md = ""
        for column in [column for column in df.columns if not pandas.isna(row[column])]:
            if column not in field_type_map:
                yml[column] = row[column].strip()
            else:
                if field_type_map[column] == list:
                    yml[column] = [x.strip() for x in row[column].split(",")]
                elif field_type_map[column] == FIELD_TYPE_MARKDOWN_SECTION:
                    md = md + "\n## {}\n{}\n\n".format(column, row[column])
                elif field_type_map[column] == datetime.date and date_format_converter is not None:
                    yml[column] = date_format_converter(row[column].strip())
                else:
                    yml[column] = row[column].strip()
        # logging.debug(yml)
        # logging.debug(yaml.dump(yml, allow_unicode=True))
        # logging.debug(yamldown.dump(yml, md))
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with codecs.open(out_file, "w", 'utf-8') as out_file_obj:
            out_file_obj.write(yamldown.dump(yml, md))



if __name__ == '__main__':
    def file_namer(row):
        # logging.debug(row['प्रारम्भः'])
        post_date = date_format_converter_us_to_yyyy_mm_dd(row['प्रारम्भः'])
        file_name = xsanscript.transliterate(row['लिङ्गम्'].strip(), xsanscript.DEVANAGARI, xsanscript.OPTITRANS)
        file_name = post_date + "_" + re.sub("[^a-zA-Z0-9\-_]", "_", file_name) + ".md"
        return file_name

    convert(
        csv_in="/home/vvasuki/Downloads/shruta-kathAH.csv",
        out_dir="/home/vvasuki/vvasuki-git/rahashtippanyah/content/sva-kathAH",
        field_type_map={
            'सूत्रम्': str,
            'विवरणम्': FIELD_TYPE_MARKDOWN_SECTION
        }, file_namer=file_namer, date_format_converter=date_format_converter_us_to_yyyy_mm_dd)