import json

import regex

from doc_curation.md.content_processor import details_helper, transliterate
from doc_curation.md.file import MdFile
from doc_curation_projects.kaavya.divyaprabandha import general
from indic_transliteration import sanscript


def process_word_meaning_json(in_path, out_path):

  with open(in_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

  references = {}

  # Populate the dictionary
  for item in data.get("results"):
    ref_id = item.get("reference_id")
    word = item.get("word")
    translation = item.get("translation")
    sort_order = item.get("sort_order")

    # Ensure all required fields are present
    if ref_id is not None and word is not None and translation is not None and sort_order is not None:
      line = f"**{word}** = {translation}"

      if ref_id not in references:
        references[ref_id] = []

      references[ref_id].append((sort_order, line))

  # Sort the reference IDs to print them in order
  sorted_ref_ids = sorted(references.keys())

  verse_details = []

  for ref_id in sorted_ref_ids:
    # Sort the lines for the current reference_id based on sort_order
    sorted_lines = (sorted(references[ref_id], key=lambda x: x[0]))
    content = '; '.join([x[1] for x in sorted_lines])

    verse_details.append(details_helper.Detail(content=content, title=f"प्रतिपदार्थः (UV) - {ref_id}"))

  content = "\n\n".join([x.to_md_html() for x in verse_details])
  md_file = MdFile(file_path=out_path)
  md_file.dump_to_file(metadata={"title": "प्रतिपदार्थः (UV)"}, content=content, dry_run=False)


def process_basic_data_json(in_path, out_path):

  with open(in_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

  id_to_basic_data = {}
  id_to_simple_verse = {}
  id_to_verse = {}
  id_to_ta_meaning = {}
  # Populate the dictionary
  for item in data.get("results"):
    ref_id = item.get("number_full")
    basic_data = {"uv_id": f"{item.get('sc')}_{item.get('pathu')}_{item.get('thirumozhi')}", "rAga": item.get('ragam'), "tAla": item.get("thalam"), "bhAva": item.get('mood')}
    id_to_basic_data[ref_id] = basic_data
    id_to_simple_verse[ref_id] = regex.sub("\\n *", "  \n", item.get("pasuram_ta"))
    id_to_verse[ref_id] = regex.sub("\\n *", "  \n", item.get("pasuram_ta_c"))
    id_to_ta_meaning[ref_id] = regex.sub("\\n *", "  \n", item.get("meaning_ta"))

  # Sort the reference IDs to print them in order
  sorted_ref_ids = sorted(id_to_basic_data.keys(), key=lambda x: int(sanscript.transliterate(x, sanscript.DEVANAGARI, sanscript.IAST)))

  verse_details = []
  for ref_id in sorted_ref_ids:
    basic_data = id_to_basic_data[ref_id]
    detail = details_helper.Detail(title=f"Info - {ref_id}", content=str(basic_data))
    verse_details.append(detail)

    simple_verse = id_to_simple_verse[ref_id]
    detail = details_helper.Detail(title=f"मूलम् (विभक्तम्) - {ref_id}", content=simple_verse)
    verse_details.append(detail)

    verse = id_to_verse[ref_id]
    detail = details_helper.Detail(title=f"मूलम् (UV) - {ref_id}", content=verse)
    verse_details.append(detail)

    ta_meaning = id_to_ta_meaning[ref_id]
    detail = details_helper.Detail(title=f"अर्थः (UV) - {ref_id}", content=ta_meaning)
    verse_details.append(detail)

  content = "\n\n".join([x.to_md_html() for x in verse_details])
  md_file = MdFile(file_path=out_path)
  md_file.dump_to_file(metadata={"title": "प्रतिपदार्थः (UV)"}, content=content, dry_run=False)



# Run the main function when the script is executed
if __name__ == "__main__":
  # process_word_meaning_json(in_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/static/4k-divya-prabandha/synonyms_ta.json", out_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/synonyms_ta.md")
  # general.devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/static/4k-divya-prabandha/uveda-basic.json", source_script="tamil")

  process_basic_data_json(in_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/static/4k-divya-prabandha/uveda-basic.json", out_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/UV/mUlam_UV.md")