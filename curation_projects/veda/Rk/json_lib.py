import codecs
import glob
import json


def get_suukta_id_to_rk_map():
  json_paths = glob.glob("/home/vvasuki/sanskrit/raw_etexts/vedaH/Rg/shakala/saMhitA/sAyaNabhAShyam/*/*/*.json", recursive=True)
  suukta_id_to_rk_map = {}
  for json_path in sorted(json_paths):
    with codecs.open(json_path, "r") as fp:
      rk = json.load(fp)
      suukta_id = "%02d/%03d" % (int(rk["classification"]["mandala"]), int(rk["classification"]["sukta"]))
      suukta_rk_map = suukta_id_to_rk_map.get(suukta_id, {})
      suukta_rk_map[rk["classification"]["rik"]] = {}
      suukta_id_to_rk_map[suukta_id] = suukta_rk_map

  return suukta_id_to_rk_map