---
name: dictionary
description: Manages Indic and Sanskrit Babylon/StarDict dictionaries — updates local StarDict installations via stardict_sanskrit.commandInterface, locates code and mirror repositories for dictionary generation and maintenance, and documents automatic .babylon_final and tarball builds.
---

# Indic & Sanskrit Dictionaries (`indic-dict`)

## 1. Updating locally installed StarDict dictionaries

Local StarDict dictionaries are installed under `/media/vvasuki/vData/dicts/stardict/` (specifically `/media/vvasuki/vData/dicts/stardict/indic-dict/`).

Run `stardict_sanskrit.commandInterface install` from `dict-tools.jar` to download and extract the latest dictionary tarballs from the release index:

```bash
java -cp ~/gitland/indic-dict/dict-tools/bin/artifacts/dict-tools.jar \
  stardict_sanskrit.commandInterface install \
  --destinationPath /media/vvasuki/vData/dicts/stardict/ \
  --dictRepoIndexUrl https://github.com/indic-dict/stardict-index/releases/download/current/dictionaryIndices.md \
  --overwrite true
```

Notes from `stardict_sanskrit/commandInterface.scala` and `installer.scala`:
- `~/gitland/indic-dict/dict-tools/bin/artifacts/dict-tools.jar` also sets `mainClass := Some("stardict_sanskrit.commandInterface")` in `build.sbt`, so `java -jar ... install ...` works equivalently.
- Optional `--dictPattern "<regex>"` filters which dictionary names get installed (defaults to `".*"`).
- Use `--overwrite false` to skip dictionaries whose local `.ifo` modification time is already newer than the tarball timestamp; use `--overwrite true` to force re-download and extraction.
- Always use the `releases/download/current/dictionaryIndices.md` URL rather than `raw.githubusercontent.com/.../master/dictionaryIndices.md` so download metrics are tracked (see `stardict-index/README.md`).
- Desktop StarDict viewer available locally: `goldendict`.

## 2. Locations of dictionary code and repositories

### Dictionary generation & curation (Python)
Repository: `~/gitland/indic-dict/dict-curation/` (run with `~/gitland/python_venv/bin/python` / `~/gitland/python_venv/bin/pytest`):
- `dict_curation/babylon/` — Core `.babylon` read, dump, clean, transliterate, headword, and language utilities (`__init__.py`, `cleaner.py`, `definitions_helper.py`, `exporter.py`, `header_helper.py`, `headwords_helper.py`, `language.py`, `lipi.py`).
- `dict_curation/stardict/` — StarDict downloader & packaging helpers (`downloader.py`, `pushtoandroid.sh`).
- `dict_curation_projects/conversion/babylon/dict_specific/` — Source-specific Babylon dictionary builders (e.g., `apte_sa.py`, `kalpadruma.py`, `vAchaspatyam.py`, `hi_shabdasAgar.py`, `datuk2babylon.py`, etc.).
- `dict_curation_projects/conversion/babylon/dict_specific/veda/` — Vedic padapāṭha svara and prakṛti-svara generators in US notation (`᳓` / `᳙`):
  - `padasvara_common.py` — shared Babylon writer & classical→US accent normalizers
  - `taittiriya.py` (`kyv-ts-padasvara`), `rgveda.py` (`rv-padasvara-dev`), `atharva.py` (`av-padasvara`), `madhyandina.py` (`syv-ms-padasvara`), `shatapatha.py` (`syv-sb-m-pada-svara` for `*SB-M*`, `syv-sb-k-pada-svara` for `*SB-K*`), `dhatupatha_svara.py` (`dhAtupAThaH_sasvaraH`)
  - `prakrti_svara.py` (`kyv-ts-prakRti-svara`, `rv-prakRti-svara-dev`, `av-prakRti-svara`, `syv-ms-prakRti-svara`, `syv-sb-m-prakRti-svara`)
- `dict_curation_projects/dump/` — Scrapers and Vidyut/vyākaraṇa generators (`vidyut_dicts.py`, `vidyut-calls.sh`, `bhagavad-go-maNDala.py`, `scrape_rkencp.py`, `shabda_kasustubha.py`, etc.; run heavy dumps on Kaggle/Colab, not locally).

### Packaging, headword expansion, CLI & CI tooling (Scala / Bash)
Repository: `~/gitland/indic-dict/dict-tools/`:
- `src/main/scala/stardict_sanskrit/commandInterface.scala` — CLI entrypoint (`install`, `makeIndicStardictTar`, `addStandardHeadwords`, `makeTars`, `makeStardict`, `makePerHeadwordMdFiles`, `writeTarsList`, `compressAllDicts`).
- `src/main/scala/stardict_sanskrit/installer.scala` — Downloads `dictionaryIndices.md` → `tars.MD` feeds → `.tar.gz` files and extracts them.
- `src/main/scala/stardict_sanskrit/batchProcessor.scala` & `DictionaryFolder.scala` — End-to-end build pipeline: `.babylon` → `.babylon_final` → StarDict binary files via `/usr/lib/stardict-tools/babylon` + `dictzip` → `.tar.gz` + `tars.MD`.
- `src/main/scala/sanskritnlp/dictionary/babylonTools.scala` & `headwordTransformers.scala` — `addStandardHeadwords` generates `.babylon_final` from `.babylon` by adding non-anusvāra variants, Devanāgarī from other Indic scripts, OPTITRANS, and (for `sa-head`, `sanskrit-kAvya`, `sanskrit-vyAkaraNa`) IAST & ISO headwords.
- `bin/bash/` — Shell wrappers (`full_build.sh`, `babylon_add_optitrans.sh`, `tsv_to_babylon.sh`, `tsv_to_stardict.sh`, `make_tarballs.sh`, `update_tars_md.sh`).
- `bin/artifacts/dict-tools.jar` — Fat JAR built via `sbt assembly`.

### Dictionary data repositories & local mirrors
- `~/gitland/indic-dict/dicts/` — Local clones of `indic-dict/stardict-*` repositories (`stardict-sanskrit`, `stardict-sanskrit-kAvya`, `stardict-sanskrit-vyAkaraNa`, `stardict-index`, etc.).
- `~/gitland/indic-dict/stardict/` — Secondary local clone mirror of `stardict-*` repositories.
- `~/gitland/sanskrit/raw_etexts/koshaH/indic-dict/` — Submodules (`kAvya/`, `sanskrit/`, `vyAkaraNa/`) read by `doc_curation` (`shatapatha_solver.py`, `provenance.py`).
- `~/gitland/indic-dict/dicts/stardict-index/dictionaryIndices.md` — Master list of `tars.MD` feeds across all `indic-dict` repos.

## 3. Build & maintenance rules

- **Do NOT generate or commit `.babylon_final` files manually**: `.gitignore` in `stardict-*` repos ignores `*.babylon_final` (along with `*.ifo`, `*.idx`, `*.syn`, `*.dict.dz`). Generators should write only `<dict>.babylon` (and `README.md`).
- **Automatic `.babylon_final` & release generation**: Each `stardict-*` repo's `makefile` + `.github/workflows/build.yml` runs `full_build.sh` (`makeIndicStardictTar`), which runs `babylonTools.addStandardHeadwords` to produce `.babylon_final`, compiles StarDict files, packages `.tar.gz`, and deploys to `gh-pages`.
- **Keep mirrors in sync**: Generators in `dict_curation_projects/.../veda/` write `.babylon` outputs to all three local mirrors (`raw_etexts/koshaH/indic-dict/kAvya`, `indic-dict/dicts/stardict-sanskrit-kAvya`, `indic-dict/stardict/stardict-sanskrit-kAvya`) when their parent directories exist; commit and push from the intended `stardict-*` repo (`dicts/...`) to trigger CI builds.
