"""Sequential core↔translation alignment via Gemini models.

Thin wrapper: builds a :class:`GeminiBackend` and drives the
provider-agnostic sweep in :mod:`doc_curation.llm.translation_matcher` with it.
"""

from doc_curation.llm import translation_matcher as _base

from .backend import GeminiBackend


def seq_match_texts_to_translation(
    texts, translation_text, model_id=None, api_key_path="gemini.vv",
    cred_path=None, **matcher_kwargs):
  """Align ``texts`` to ``translation_text`` using a Gemini model.

  :param model_id: default ``gemini-3.5-flash``.
  :param api_key_path: key id for the shared TOML store.
  :param matcher_kwargs: passed to
    :func:`doc_curation.llm.translation_matcher.seq_match_texts_to_translation`
    (``batch_core_chars``, ``window_en_chars``, ``max_retries``).
  :return: list of translation strings, ``len == len(texts)``.
  """
  backend = GeminiBackend(api_key_path=api_key_path, model_id=model_id,
                          cred_path=cred_path)

  def generate_fn(prompt):
    text, _metadata = backend.generate_content([prompt], model_id=model_id)
    return text

  return _base.seq_match_texts_to_translation(
    texts, translation_text, generate_fn, **matcher_kwargs)


def insert_translation_details(md_path, translation_dir_path, start_file=None,
                             end_file=None, end_after=None, model_id=None,
                             api_key_path="gemini.vv", cred_path=None,
                             **matcher_kwargs):
  """Interleave translations into ``md_path`` (in place) via Gemini model.

  Assumes :func:`doc_curation.md.content_processor.details.maker.generic_sanskrit_vipra_mUla`
  has already run (every sentence already sits in its own मूलम् block):
  gathers the मूलम् sentences, maps them with
  :func:`seq_match_texts_to_translation`, and inserts just the Translation
  [/ Notes] details above each corresponding मूलम् block.  Cores with no
  counterpart are skipped (marker only, no empty block); see the base
  module for the protocol.

  :param translation_dir_path: directory of translation ``*.md`` files,
    or a single translation ``*.md`` file path.
  :param start_file: basename to start from; ``None`` starts first.
  :param end_file: basename to stop at (inclusive); ``None`` runs to the
    last file.
  :param end_after: distinctive phrase from the last in-scope unit,
    matched locally (no LLM); the stream truncates after its unit.
  :return: dict summary (sentences, paragraphs, notes, empty, skipped,
    files).
  """
  backend = GeminiBackend(api_key_path=api_key_path, model_id=model_id,
                          cred_path=cred_path)

  def generate_fn(prompt):
    text, _metadata = backend.generate_content([prompt], model_id=model_id)
    return text

  return _base.insert_translation_details(
    md_path, translation_dir_path, start_file=start_file, end_file=end_file,
    end_after=end_after, generate_fn=generate_fn, **matcher_kwargs)
