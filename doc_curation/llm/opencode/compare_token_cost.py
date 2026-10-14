"""Compare LLM input-token cost of Devanagari vs SLP1 Sanskrit, per model.

Motivation: the interleaving matcher (:mod:`doc_curation.llm.translation_matcher`)
sends Sanskrit core texts to a model in the *raw* script. Whether romanising
them to SLP1 saves tokens depends entirely on the model's tokenizer (dev/
roman/text), which is best measured rather than guessed.

This utility sends the *real* alignment prompt (built by
``translation_matcher._prompt_for_batch``) once per script variant per model
and reports the ``tokens.input`` each call consumes. A fixed CLI/system
overhead is present in both variants and cancels in the delta, so compare
the delta (and the delta as a fraction of the Devanagari input).

Usage::

    python -m doc_curation.llm.opencode.compare_token_cost
    python -m doc_curation.llm.opencode.compare_token_cost \
        --models muse-spark-1.3-contributor,step-5-preview-free \
        --api-key-path opencode.vv_zen
"""

import argparse
import logging
import time

from doc_curation.llm.translation_matcher import (
  _content_words, _prompt_for_batch)

#: Default models to probe (bare names are treated as opencode-go/*).
DEFAULT_MODELS = (
  "muse-spark-1.3-contributor",
  "step-5-preview-free",
  "deepseek-v4.1-flash",
  "longcat-2.5-preview-free",
)

#: Representative core batch: prose, a Sūtra-numbered lookup, a quoted
#: śruti with a Devanagari reference, and a quoted verse (multi-sentence).
DEFAULT_CORE_TEXTS = (
  "तत्राविद्यावस्थायां ब्रह्मण उपास्योपासकादिलक्षणः सर्वो व्यवहारः।",
  "तत्र कानिचिद्ब्रह्मण उपासनान्यभ्युदयार्थानि, कानिचित्क्रममुक्त्यर्थानि, "
  "कानिचित्कर्मसमृद्ध्यर्थानि।",
  "तेषां गुणविशेषोपाधिभेदेन भेदः।",
  "एक एव तु परमात्मेश्वरस्तैस्तैर्गुणविशेषैर्विशिष्ट उपास्यो यद्यपि भवति, "
  "तथापि यथागुणोपासनमेव फलानि भिद्यन्ते;",
  "‘तं यथा यथोपासते तदेव भवति’ इति श्रुतेः, "
  "‘यथाक्रतुरस्मिल्ँलोके पुरुषो भवति, तथेतः प्रेत्य भवति’ "
  "(छा. उ. ३। १४। १) इति च।",
  "स्मृतेश्च — ‘यं यं वापि स्मरन्भावं त्यजत्यन्ते कलेबरम्। "
  "तं तमेवैति कौन्तेय सदा तद्भावभावितः’ (भ. गी. ८। ६) इति ।",
)

#: Representative translation window (matches DEFAULT_CORE_TEXTS topic).
DEFAULT_TRANSLATION_TEXT = (
  "As long as it is the object of Nescience, there are applied to it the "
  "categories of devotee, object of devotion, and the like. The different "
  "modes of devotion lead to different results, some to exaltation, some to "
  "gradual emancipation, some to success in works; those modes are distinct "
  "on account of the distinction of the different qualities and limiting "
  "conditions.\n\n"
  "And although the one highest Self only, i.e. the Lord distinguished by "
  "those different qualities constitutes the object of devotion, still the "
  "fruits of devotion are distinct, according as the devotion refers to "
  "different qualities. Thus Scripture says, 'According as man worships "
  "him, that he becomes;' and, 'According to what his thought is in this "
  "world, so will he be when he has departed this life' (Cḥ. Up. III, 14, 1).\n\n"
  "Smr̥ti also makes an analogous statement, 'Remembering whatever form of "
  "being he leaves this body in the end, into that form he enters, being "
  "impressed with it through his constant meditation' (Bha. Gītā VIII, 6)."
)

#: Appended to every probe: keeps the *output* tiny (and identical across
#: variants, so the input-token delta is unaffected).
MINIMAL_OUTPUT_SUFFIX = (
  "\n\nYou need not produce the JSON. Reply with the single word: OK")


def dev_to_slp1(data):
  """Devanagari → SLP1, bypassing the editable install's broken shortcuts.

  ``indic_transliteration.sanscript.transliterate`` crashes here because a
  SLP1 shortcut value is a list, so we run the same scheme-map conversion
  minus the broken ``to_scheme.apply_shortcuts`` normalisation.

  :param data: Devanagari text.
  :return: SLP1 text (pure ASCII), or ``""`` if transliteration is
    unavailable (caller should then skip the comparison).
  """
  try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import _get_scheme_map
    from indic_transliteration.sanscript.brahmic_mapper import _brahmic
    scheme_map = _get_scheme_map(sanscript.DEVANAGARI, sanscript.SLP1)
    data = scheme_map.from_scheme.unapply_shortcuts(data_in=data)
    return _brahmic(data, scheme_map,
                    togglers={}, suspend_on=set(), suspend_off=set())
  except Exception as ex:  # pragma: no cover - environment-dependent
    logging.warning("SLP1 transliteration unavailable (%s); "
                    "run with --only-devanagari", ex)
    return ""


def build_prompt(core_texts, translation_text, slp1=False):
  """The real alignment prompt for ``core_texts`` (optionally romanised)."""
  core = list(core_texts)
  if slp1:
    core = [dev_to_slp1(t) for t in core]
    if not all(core):
      raise RuntimeError("SLP1 translocation failed; cannot build prompt.")
  en_words = _content_words(translation_text)
  return _prompt_for_batch(core, 0, en_words, 0, len(core), len(en_words)
                           ) + MINIMAL_OUTPUT_SUFFIX


def probe_model(backend, model_id, prompts):
  """Run ``prompts`` through one model; return {label: tokens dict}."""
  out = {}
  for label, prompt in prompts.items():
    _text, metadata = backend.generate_content([prompt], model_id=model_id)
    tokens = metadata.get("tokens") or {}
    out[label] = {
      "input": tokens.get("input"),
      "output": tokens.get("output"),
      "total": tokens.get("total"),
      "cost": metadata.get("cost"),
    }
  return out


def compare_token_cost(core_texts=None, translation_text=None, models=None,
                       api_key_path="opencode_go.vv_go", cred_path=None,
                       timeout=None, only_devanagari=False):
  """Measure Devanagari vs SLP1 input-token cost for each model.

  :param core_texts: Sanskrit sentences; defaults to DEFAULT_CORE_TEXTS.
  :param translation_text: translation body; defaults to
    DEFAULT_TRANSLATION_TEXT.
  :param models: model ids (bare names → ``opencode-go/``); defaults to
    DEFAULT_MODELS.
  :param api_key_path: key id in the shared TOML store.
  :param only_devanagari: skip the SLP1 variant (e.g. transliteration
    unavailable) and just report the Devanagari baseline.
  :return: {model_id: {"dev": tokens, "slp1": tokens, "delta": int,
    "saving_pct": float|None, "core_chars": int, "prompt_chars": int}}
  """
  from doc_curation.llm.opencode.backend import OpencodeBackend

  core_texts = list(core_texts or DEFAULT_CORE_TEXTS)
  translation_text = translation_text or DEFAULT_TRANSLATION_TEXT
  models = list(models or DEFAULT_MODELS)

  prompts = {"dev": build_prompt(core_texts, translation_text, slp1=False)}
  slp_ok = not only_devanagari
  if slp_ok:
    try:
      prompts["slp1"] = build_prompt(core_texts, translation_text, slp1=True)
    except RuntimeError:
      slp_ok = False
      logging.warning("Skipping SLP1 probes (translocation unavailable).")

  kwargs = {} if timeout is None else {"timeout": timeout}
  backend = OpencodeBackend(api_key_path=api_key_path, model_id=models[0],
                            cred_path=cred_path, **kwargs)

  results = {}
  header = f"{'model':38} {'dev in':>7} {'slp1 in':>8} {'delta':>7} {'save%':>7}"
  print(header)
  print("-" * len(header))
  for model in models:
    model_id = model if "/" in model else f"opencode-go/{model}"
    counts = probe_model(backend, model_id, prompts)
    dev_in = counts["dev"]["input"] or 0
    delta = saving = None
    if slp_ok and counts.get("slp1"):
      slp_in = counts["slp1"]["input"] or 0
      delta = slp_in - dev_in
      saving = (100.0 * delta / dev_in) if dev_in else None
    entry = {
      "dev": counts["dev"],
      "slp1": counts.get("slp1"),
      "delta": delta,
      "saving_pct": saving,
      "core_chars": sum(len(t) for t in core_texts),
      "prompt_chars": len(prompts["dev"]),
    }
    results[model_id] = entry
    print(f"{model_id:38} {dev_in:7d} "
          f"{(entry['slp1'] or {}).get('input', 0):8d} "
          f"{(delta if delta is not None else 0):7d} "
          f"{(f'{saving:+.1f}' if saving is not None else 'n/a'):>7}")
  return results


def _parse_args(argv=None):
  parser = argparse.ArgumentParser(
    description="Compare Devanagari vs SLP1 input-token cost per opencode model.")
  parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                      help="comma-separated model ids (bare → opencode-go/)")
  parser.add_argument("--api-key-path", default="opencode.vv_zen")
  parser.add_argument("--cred-path", default=None)
  parser.add_argument("--timeout", type=float, default=None)
  parser.add_argument("--only-devanagari", action="store_true",
                      help="skip the SLP1 variant")
  return parser.parse_args(argv)


def main(argv=None):
  args = _parse_args(argv)
  logging.basicConfig(level=logging.INFO,
                      format="%(levelname)s %(name)s: %(message)s")
  models = [m.strip() for m in args.models.split(",") if m.strip()]
  results = compare_token_cost(
    models=models, api_key_path=args.api_key_path, cred_path=args.cred_path,
    timeout=args.timeout, only_devanagari=args.only_devanagari)
  total_cost = sum((r["dev"].get("cost") or 0)
                   + ((r["slp1"] or {}).get("cost") or 0)
                   for r in results.values())
  print(f"\nRuns: {len(results)} model(s) x "
        f"{2 if any(r['slp1'] for r in results.values()) else 1} variant(s); "
        f"reported cost {total_cost:.2e}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
