"""Configuration, data.toml loader, and shared compiled constants for VS-K samhitaa."""
from __future__ import annotations

import pathlib
import re
import tomllib

_DATA = tomllib.loads((pathlib.Path(__file__).with_name("data.toml")).read_text(encoding="utf-8"))

VSK_SAMHITA_DIR = pathlib.Path(_DATA["paths"]["vsk_samhita_dir"])
VSK_SARVA_PRASTUTI_DIR = VSK_SAMHITA_DIR / "sarva-prastutiH"
VSM_SARVA_PRASTUTI_DIR = pathlib.Path(_DATA["paths"]["vsm_sarva_prastuti_dir"])
KANVA_PDF_DIR = pathlib.Path(_DATA["paths"]["kanva_pdf_dir"])

KANVA_AVATARIKA_SPECS = tuple(
  (s["key"], s["avatarika"], s["viniyoga"]) for s in _DATA["avatarika_specs"]
)
KANVA_TIKA_SPECS = tuple((s["key"], s["label"]) for s in _DATA["tika_specs"])

_ACCENTS_STR = _DATA["constants"]["accents_str"]
_VP_STRIP_RE = re.compile(rf"[{_ACCENTS_STR}]")

_VSK_40_16_MISSING_MULA = _DATA["constants"]["vsk_40_16_missing_mula"]
_VSK_40_16_MISSING_VP = _DATA["constants"]["vsk_40_16_missing_vp"]
_KANDIKA_40_16_HEADER_WORDS_CHECK = _DATA["constants"]["kandika_40_16_header_words_check"]

_DEV_ORDINALS_CH: dict[int, str] = {int(k): v for k, v in _DATA["ordinals"].items()}
_DEV_ORDINAL_EXTRAS: dict[int, list[str]] = {
  int(k): list(v) for k, v in _DATA["ordinal_extras"].items()
}

_VSM_APPARATUS_RE = re.compile(_DATA["patterns"]["vsm_apparatus"])
# Note: preserve apostrophe inside character class cleanly in TOML + add single quote alternation here
_VSM_HEADER_RE = re.compile(_DATA["patterns"]["vsm_header"].replace('"', "'\""))
_COMMENTARY_PROSE_RE = re.compile(_DATA["patterns"]["commentary_prose"])
