"""Opencode LLM helpers (Muse Spark and other opencode models via the opencode CLI,
sharing llm chunkers).

The retry/rotation engine is provider-agnostic (it classifies errors by
HTTP-ish status codes and message text, and persists key statuses to the
shared TOML store), so it is reused from gemini.rotator rather than
duplicated.

The model is fully variable: pass any ``provider/model`` id visible in
``opencode models`` as ``model_id`` (e.g. ``"opencode-go/muse-spark-1.3-contributor"``
— the default — or ``"opencode/longcat-2.5-preview-free"``). A bare name
without ``/`` is assumed to live under ``opencode-go/``.
"""
from doc_curation.llm.detail_chunker import process_details
from doc_curation.llm.gemini.rotator import _call_with_keys
from doc_curation.llm.pdf_chunker import process_pdf_chunks
from doc_curation.llm.text_chunker import process_text_chunks

from .backend import OpencodeBackend, OpencodeChat, OpencodeError, OpencodeFileRef, OpencodeTimeoutError
from .keys import get_client


def _opencode_text_chunks_fn(*args, api_key_path=None, model_id=None, cred_path=None,
                             timeout=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend_args = {} if timeout is None else {"timeout": timeout}
    backend = OpencodeBackend(api_key_path=api_key_path or "opencode.vv_zen",
                              model_id=model_id, cred_path=cred_path, **backend_args)
  return process_text_chunks(*args, backend=backend, **kwargs)


def _opencode_details_fn(*args, api_key_path=None, model_id=None, cred_path=None,
                         timeout=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend_args = {} if timeout is None else {"timeout": timeout}
    backend = OpencodeBackend(api_key_path=api_key_path or "opencode.vv_zen",
                              model_id=model_id, cred_path=cred_path, **backend_args)
  return process_details(*args, backend=backend, **kwargs)


def _opencode_pdf_chunks_fn(*args, api_key_path=None, model_id=None, cred_path=None,
                            timeout=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend = OpencodeBackend(api_key_path=api_key_path or "opencode.vv_zen",
                              model_id=model_id, cred_path=cred_path,
                              **({} if timeout is None else {"timeout": timeout}))
  return process_pdf_chunks(*args, backend=backend, **kwargs)


def process_text_chunks_with_keys(file_in, *args, api_key_path="opencode", cred_path=None,
                                  model_id=None, max_attempts=None, max_transient_retries=8,
                                  **kwargs):
  """Process a text file chunk-by-chunk; model_id picks any opencode model
  (default: opencode-go/muse-spark-1.3-contributor)."""
  return _call_with_keys(_opencode_text_chunks_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, model_id=model_id, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries,
                         product="Opencode", **kwargs)


def process_details_with_keys(file_in, *args, api_key_path="opencode", cred_path=None,
                              model_id=None, max_attempts=None, max_transient_retries=8,
                              **kwargs):
  """Process <details> blocks; model_id picks any opencode model
  (default: opencode-go/muse-spark-1.3-contributor)."""
  return _call_with_keys(_opencode_details_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, model_id=model_id, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries, **kwargs)


def process_pdf_chunks_with_keys(file_in, *args, api_key_path="opencode", cred_path=None,
                                 model_id=None, max_attempts=None, max_transient_retries=8,
                                 **kwargs):
  """Process PDF chunks; model_id picks any opencode model
  (default: opencode-go/muse-spark-1.3-contributor)."""
  return _call_with_keys(_opencode_pdf_chunks_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, model_id=model_id, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries, **kwargs)


__all__ = [
    "OpencodeBackend",
    "OpencodeChat",
    "OpencodeError",
    "OpencodeFileRef",
    "OpencodeTimeoutError",
    "get_client",
    "process_text_chunks",
    "process_details",
    "process_pdf_chunks",
    "process_text_chunks_with_keys",
    "process_details_with_keys",
    "process_pdf_chunks_with_keys",
]
