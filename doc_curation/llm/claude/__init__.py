"""Claude LLM helpers (Anthropic-backed, sharing llm chunkers).

The retry/rotation engine is provider-agnostic (it classifies errors by
HTTP status codes and message text, and persists key statuses to the
shared TOML store), so it is reused from gemini.rotator rather than
duplicated.
"""
from doc_curation.llm.detail_chunker import process_details
from doc_curation.llm.gemini.rotator import _call_with_keys
from doc_curation.llm.pdf_chunker import process_pdf_chunks
from doc_curation.llm.text_chunker import process_text_chunks

from .backend import ClaudeBackend, ClaudeChat
from .keys import get_client


def _claude_text_chunks_fn(*args, api_key_path=None, model_id=None, max_tokens=None, cred_path=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend = ClaudeBackend(api_key_path=api_key_path or "claude.default",
                            model_id=model_id, max_tokens=max_tokens, cred_path=cred_path)
  return process_text_chunks(*args, backend=backend, **kwargs)


def _claude_details_fn(*args, api_key_path=None, model_id=None, max_tokens=None, cred_path=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend = ClaudeBackend(api_key_path=api_key_path or "claude.default",
                            model_id=model_id, max_tokens=max_tokens, cred_path=cred_path)
  return process_details(*args, backend=backend, **kwargs)


def _claude_pdf_chunks_fn(*args, api_key_path=None, model_id=None, max_tokens=None, cred_path=None, **kwargs):
  kwargs = dict(kwargs)
  backend = kwargs.pop("backend", None)
  if backend is None:
    backend = ClaudeBackend(api_key_path=api_key_path or "claude.default",
                            model_id=model_id, max_tokens=max_tokens, cred_path=cred_path)
  return process_pdf_chunks(*args, backend=backend, **kwargs)


def process_text_chunks_with_keys(file_in, *args, api_key_path="claude", cred_path=None,
                                  max_attempts=None, max_transient_retries=8, **kwargs):
  return _call_with_keys(_claude_text_chunks_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries, **kwargs)


def process_details_with_keys(file_in, *args, api_key_path="claude", cred_path=None,
                              max_attempts=None, max_transient_retries=8, **kwargs):
  return _call_with_keys(_claude_details_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries, **kwargs)


def process_pdf_chunks_with_keys(file_in, *args, api_key_path="claude", cred_path=None,
                                 max_attempts=None, max_transient_retries=8, **kwargs):
  return _call_with_keys(_claude_pdf_chunks_fn, file_in, *args, api_key_path=api_key_path,
                         cred_path=cred_path, max_attempts=max_attempts,
                         max_transient_retries=max_transient_retries, **kwargs)


__all__ = [
    "ClaudeBackend",
    "ClaudeChat",
    "get_client",
    "process_text_chunks",
    "process_details",
    "process_pdf_chunks",
    "process_text_chunks_with_keys",
    "process_details_with_keys",
    "process_pdf_chunks_with_keys",
]
