
import codecs
import logging
from collections import defaultdict

from sanskrit_data import collection_helper
import json

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def group_equivalent_classes(css_json, definition_filter=None):
  # Can convert css to json using https://staxmanade.com/CssToReact/
  try:
    css_dict = json.loads(css_json)
  except Exception:
    with codecs.open(css_json, "r") as f:
      css_dict = json.load(fp=f)
  definition_to_class = defaultdict(set)
  for class_id, definition in css_dict.items():
    if definition_filter is not None:
      definition = definition_filter(definition)
    definition_str = json.dumps(definition, sort_keys=True)
    definition_to_class[definition_str].add(class_id)
  logging.info(f"Got {len(definition_to_class)} groups from {len(css_dict)} classes")
  return definition_to_class


def print_equivalent_classes(css_json, definition_filter=None):
  definition_to_class = group_equivalent_classes(css_json=css_json, definition_filter=definition_filter)
  for definition_str, class_set in definition_to_class.items():
    logging.info(f"{json.dumps(sorted(list(class_set)))}")


if __name__ == '__main__':
  keys = {"fontFamily", "fontSize", "fontWeight", "fontStyle", "textAlign", "color"}
  definition_to_class = print_equivalent_classes(css_json="/home/vvasuki/sanskrit/raw_etexts/purANam/mahAbhAratam/gp/epub_no_img/stylesheet.css.json", definition_filter=lambda x: collection_helper.filter_for_keys(x, keys))