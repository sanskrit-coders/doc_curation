"""Sequential core↔translation alignment via opencode models.

Thin wrapper: builds an :class:`OpencodeBackend` and drives the
provider-agnostic sweep in :mod:`doc_curation.llm.translation_matcher` with it.
"""

from doc_curation.llm import translation_matcher as _base

from .backend import OpencodeBackend


def seq_match_texts_to_translation(
    texts, translation_text, model_id=None, api_key_path="opencode.vv_zen",
    cred_path=None, timeout=None, **matcher_kwargs):
  """Align ``texts`` to ``translation_text`` using an opencode model.

  :param model_id: e.g. ``"opencode-go/muse-spark-1.3-contributor"``
    (default); a bare name is assumed under ``opencode-go/``.
  :param api_key_path: key id for the shared TOML store.
  :param timeout: per-call seconds (None = backend default).
  :param matcher_kwargs: passed to
    :func:`doc_curation.llm.translation_matcher.seq_match_texts_to_translation`
    (``batch_core_chars``, ``window_en_chars``, ``max_retries``).
  :return: list of translation strings, ``len == len(texts)``.
  """
  kwargs = {} if timeout is None else {"timeout": timeout}
  backend = OpencodeBackend(api_key_path=api_key_path, model_id=model_id,
                            cred_path=cred_path, **kwargs)

  def generate_fn(prompt):
    text, _metadata = backend.generate_content([prompt], model_id=model_id)
    return text

  return _base.seq_match_texts_to_translation(
    texts, translation_text, generate_fn, **matcher_kwargs)


def insert_translation_details(md_path, translation_dir_path, start_file=None,
                             model_id=None, api_key_path="opencode.vv_zen",
                             cred_path=None, timeout=None, **matcher_kwargs):
  """Interleave translations into ``md_path`` (in place) via opencode model.

  Assumes :func:`doc_curation.md.content_processor.details.maker.generic_sanskrit_vipra_mUla`
  has already run (every sentence already sits in its own मूलम् block):
  gathers the मूलम् sentences, maps them with
  :func:`seq_match_texts_to_translation`, and inserts just the Translation
  [/ Notes] details above each corresponding मूलम् block.

  :param translation_dir_path: directory of translation ``*.md`` files,
    or a single translation ``*.md`` file path.
  :param start_file: basename to start from; ``None`` starts first.
  :return: dict summary (sentences, paragraphs, notes, empty, files).
  """
  kwargs = {} if timeout is None else {"timeout": timeout}
  backend = OpencodeBackend(api_key_path=api_key_path, model_id=model_id,
                            cred_path=cred_path, **kwargs)

  def generate_fn(prompt):
    text, _metadata = backend.generate_content([prompt], model_id=model_id)
    return text

  return _base.insert_translation_details(
    md_path, translation_dir_path, start_file, generate_fn,
    **matcher_kwargs)
