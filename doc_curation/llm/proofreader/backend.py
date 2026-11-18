"""OpenAI-compatible ``LlmBackend`` for the Sanskrit proofreader / interleaver LLM.

Works against:
- ``vLLM`` serving ``Qwen/Qwen3-14B-AWQ`` (1×T4 Colab/Kaggle) or ``Qwen/Qwen3-32B-AWQ``
  (2×T4 Kaggle) with ``--enable-lora`` over an HTTP tunnel or local port,
- ``llama-server`` (GGUF), or
- ``ollama``'s OpenAI-compatible ``/v1/chat/completions`` endpoint.

Plugs directly into ``doc_curation.llm.text_chunker.process_text_chunks``,
``doc_curation.llm.detail_chunker``, ``doc_curation.llm.translation_matcher``,
``interleave_helper``, and ``accent_helper``.
"""
from __future__ import annotations

import os
from typing import Any
import regex
import requests

from doc_curation.llm.backend import LlmBackend, LlmChat
from .guards import enforce_post_guards, mask_protected_blocks, restore_protected_blocks
from .interleave_helper import annotate_translation_matcher_prompt
from .kaggle_jobs.kaggle_runner import DEFAULT_LOCAL_ADAPTER_DIR
from .prompts import build_system_prompt

# Wrapper prefix added by text_chunker.process_text_chunks around each chunk;
# stripped before post-guard comparison against the raw input chunk.
_CHUNK_HEADER_RE = regex.compile(
  r"^Process text chunk \d+ of \d+ according to the system instructions:\s*\n\n",
  flags=regex.DOTALL,
)


class ProofreaderChat(LlmChat):
  """Chat session that optionally applies deterministic ``मूलम्`` masking & post-guards.

   Note: Unlike frontier conversational workflows, chunk-by-chunk proofreading with
  a 14B model is both faster and cleaner when each chunk is sent as an independent
  ``[system, user]`` request (``stateless_chunks=True``), preventing KV-cache bloat
  across 100+ chunks of a book.
  """

  def __init__(
    self,
    backend: "ProofreaderBackend",
    system_prompt: str,
    model_id: str,
    *,
    apply_guards: bool = True,
    allow_suggestions: bool = True,
    stateless_chunks: bool = True,
  ):
    self._backend = backend
    self._system_prompt = system_prompt
    self._model_id = model_id
    self._apply_guards = apply_guards
    self._allow_suggestions = allow_suggestions
    self._stateless_chunks = stateless_chunks
    self._history: list[dict[str, str]] = []
    self._last_meta: dict[str, Any] = {}

  def send_text(self, text: str) -> str:
    header_m = _CHUNK_HEADER_RE.match(text or "")
    raw_body = text[header_m.end():] if header_m else (text or "")

    if self._apply_guards:
      masked_body, masks = mask_protected_blocks(raw_body)
      user_msg = masked_body
    else:
      masks = {}
      user_msg = text or ""

    messages = [{"role": "system", "content": self._system_prompt}]
    if not self._stateless_chunks:
      messages.extend(self._history)
    messages.append({"role": "user", "content": user_msg})

    reply, meta = self._backend._chat_completion(messages, model_id=self._model_id)
    self._last_meta = meta

    if self._apply_guards:
      guarded = enforce_post_guards(
        masked_body, reply, allow_suggestions=self._allow_suggestions
      )
      final_text = restore_protected_blocks(guarded, masks)
    else:
      final_text = reply

    if not self._stateless_chunks:
      self._history.append({"role": "user", "content": user_msg})
      self._history.append({"role": "assistant", "content": reply})
    return final_text

  def send_parts(self, parts: list) -> str:
    joined = "\n\n".join(str(p) for p in parts if p is not None)
    return self.send_text(joined)

  def last_metadata(self) -> dict:
    return dict(self._last_meta)


class ProofreaderBackend(LlmBackend):
  """OpenAI-compatible ``LlmBackend`` with Qwen3 ``enable_thinking=False`` & guards."""

  DEFAULT_MODEL = "sanskrit-proofreader"
  PROVIDER_TAG = "Proofreader"

  def __init__(
    self,
    base_url: str | None = None,
    model_id: str | None = None,
    api_key: str | None = None,
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: int = 300,
    enable_thinking: bool = False,
    apply_guards: bool = True,
    allow_suggestions: bool = True,
    stateless_chunks: bool = True,
  ):
    self.base_url = (
      base_url
      or os.environ.get("PROOFREADER_API_BASE")
      or "http://localhost:8000/v1"
    ).rstrip("/")
    self.model = model_id or os.environ.get("PROOFREADER_MODEL") or self.DEFAULT_MODEL
    self.api_key = api_key or os.environ.get("PROOFREADER_API_KEY") or "EMPTY"
    self.temperature = temperature
    self.max_tokens = max_tokens
    self.timeout = timeout
    self.enable_thinking = enable_thinking
    self.apply_guards = apply_guards
    self.allow_suggestions = allow_suggestions
    self.stateless_chunks = stateless_chunks
    self.local_adapter_dir = os.environ.get("PROOFREADER_ADAPTER_DIR") or DEFAULT_LOCAL_ADAPTER_DIR

  def _chat_completion(
    self,
    messages: list[dict[str, str]],
    model_id: str | None = None,
  ) -> tuple[str, dict]:
    url = f"{self.base_url}/chat/completions"
    payload: dict[str, Any] = {
      "model": model_id or self.model,
      "messages": messages,
      "temperature": self.temperature,
      "max_tokens": self.max_tokens,
      "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
    }
    headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {self.api_key}",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"].get("content") or ""
    return content, data.get("usage", {})

  def new_chat(self, system_prompt: str, model_id: str | None = None) -> ProofreaderChat:
    # Automatically disable proofreading lexical guards if called with JSON/interleaver prompt
    is_json_task = "ONLY valid JSON" in system_prompt or "ONLY this JSON" in system_prompt
    return ProofreaderChat(
      self,
      system_prompt=system_prompt,
      model_id=model_id or self.model,
      apply_guards=self.apply_guards and not is_json_task,
      allow_suggestions=self.allow_suggestions,
      stateless_chunks=self.stateless_chunks,
    )

  def upload_file(self, path: str) -> Any:
    with open(path, encoding="utf-8") as f:
      return f.read()

  def generate_content(
    self,
    contents: list | str,
    model_id: str | None = None,
  ) -> tuple[str, dict]:
    """Single-shot generation (used directly by ``translation_matcher``, etc.)."""
    if isinstance(contents, str):
      prompt_text = contents
    else:
      prompt_text = "\n\n".join(str(c) for c in contents if c is not None)
    prompt_text = annotate_translation_matcher_prompt(prompt_text)
    messages = [{"role": "user", "content": prompt_text}]
    text, meta = self._chat_completion(messages, model_id=model_id)
    # Strip any stray <think> wrapper while leaving JSON intact
    text = regex.sub(r"^\s*<think>.*?</think>\s*", "", text, flags=regex.DOTALL)
    return text, meta


def proofread_text(
  text: str,
  *,
  backend: ProofreaderBackend | None = None,
  clause_newlines: bool = True,
  suggest_corrections: bool = True,
  markdown_cleanup: bool = True,
  extra_instructions: str = "",
) -> str:
  """Convenience wrapper to proofread & hyphenate a Markdown string."""
  b = backend or ProofreaderBackend(allow_suggestions=suggest_corrections)
  prompt = build_system_prompt(
    clause_newlines=clause_newlines,
    suggest_corrections=suggest_corrections,
    markdown_cleanup=markdown_cleanup,
    extra_instructions=extra_instructions,
  )
  chat = b.new_chat(system_prompt=prompt)
  return chat.send_text(text)
