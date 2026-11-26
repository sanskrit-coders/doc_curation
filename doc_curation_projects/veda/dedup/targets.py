"""Typed registry of Vedic śākhā corpora loaded from `cross_veda_targets.toml`."""
from __future__ import annotations

import dataclasses
import functools
import pathlib
import tomllib

CONFIG_PATH = pathlib.Path(__file__).with_name("cross_veda_targets.toml")


@dataclasses.dataclass(frozen=True)
class VedaCorpusSpec:
  """Paths, Hugo URL prefixes, and commentary qualification labels for one Vedic śākhā/layer."""

  name: str
  shAkha_label: str
  pada_label: str
  sayana_variant_label: str
  bb_variant_label: str = ""
  keith_variant_label: str = ""
  dayananda_qual: str = ""
  has_two_part_rk: bool = False
  content_dir: pathlib.Path | None = None
  vp_dir: pathlib.Path | None = None
  sarva_dir: pathlib.Path | None = None
  vp_url_prefix: str = ""
  sarva_url_prefix: str = ""
  yajuh_vp_dir: pathlib.Path | None = None
  yajuh_vp_url: str = ""
  yajuh_sarva_dir: pathlib.Path | None = None
  yajuh_sarva_url: str = ""
  yajuh_sarva_prastuti_dir: pathlib.Path | None = None
  yajuh_sarva_prastuti_url: str = ""
  brahmana_vp_dir: pathlib.Path | None = None
  brahmana_vp_url: str = ""
  brahmana_sarva_dir: pathlib.Path | None = None
  brahmana_sarva_url: str = ""
  brahmana_sarva_prastuti_dir: pathlib.Path | None = None
  brahmana_sarva_prastuti_url: str = ""
  heading_level: int = 0


def _opt_path(raw: dict, key: str) -> pathlib.Path | None:
  val = raw.get(key)
  return pathlib.Path(val) if val else None


@functools.lru_cache(maxsize=4)
def load_corpus_specs(config_path: pathlib.Path = CONFIG_PATH) -> dict[str, VedaCorpusSpec]:
  """Load `cross_veda_targets.toml` into `name -> VedaCorpusSpec`."""
  data = tomllib.loads(config_path.read_text(encoding="utf-8"))
  specs: dict[str, VedaCorpusSpec] = {}
  for name, entry in data["corpora"].items():
    specs[name] = VedaCorpusSpec(
      name=entry["name"],
      shAkha_label=entry["shAkha_label"],
      pada_label=entry["pada_label"],
      sayana_variant_label=entry["sayana_variant_label"],
      bb_variant_label=entry.get("bb_variant_label", ""),
      keith_variant_label=entry.get("keith_variant_label", ""),
      dayananda_qual=entry.get("dayananda_qual", ""),
      has_two_part_rk=bool(entry.get("has_two_part_rk", False)),
      content_dir=_opt_path(entry, "content_dir"),
      vp_dir=_opt_path(entry, "vp_dir"),
      sarva_dir=_opt_path(entry, "sarva_dir"),
      vp_url_prefix=entry.get("vp_url_prefix", ""),
      sarva_url_prefix=entry.get("sarva_url_prefix", ""),
      yajuh_vp_dir=_opt_path(entry, "yajuh_vp_dir"),
      yajuh_vp_url=entry.get("yajuh_vp_url", ""),
      yajuh_sarva_dir=_opt_path(entry, "yajuh_sarva_dir"),
      yajuh_sarva_url=entry.get("yajuh_sarva_url", ""),
      yajuh_sarva_prastuti_dir=_opt_path(entry, "yajuh_sarva_prastuti_dir"),
      yajuh_sarva_prastuti_url=entry.get("yajuh_sarva_prastuti_url", ""),
      brahmana_vp_dir=_opt_path(entry, "brahmana_vp_dir"),
      brahmana_vp_url=entry.get("brahmana_vp_url", ""),
      brahmana_sarva_dir=_opt_path(entry, "brahmana_sarva_dir"),
      brahmana_sarva_url=entry.get("brahmana_sarva_url", ""),
      brahmana_sarva_prastuti_dir=_opt_path(entry, "brahmana_sarva_prastuti_dir"),
      brahmana_sarva_prastuti_url=entry.get("brahmana_sarva_prastuti_url", ""),
      heading_level=int(entry.get("heading_level", 0) or 0),
    )
  return specs
