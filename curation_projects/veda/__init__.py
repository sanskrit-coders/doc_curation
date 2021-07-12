import glob
import os


def get_Rk_id_to_name_map_from_mUlam():
  Rk_paths = glob.glob("/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/mUlam/*/*/*.md", recursive=True)
  Rk_paths = sorted(Rk_paths)
  Rk_id_to_name_map = {}
  for Rk_path in Rk_paths:
    Rk_name = os.path.basename(Rk_path).replace(".md", "")
    Rk_id_numerical = "/".join(Rk_path.split("/")[-3:-1]) + "_" + Rk_name.split("_")[0]
    Rk_id_to_name_map[Rk_id_numerical] = Rk_name
  return Rk_id_to_name_map