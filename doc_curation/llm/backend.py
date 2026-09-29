"""Shared LLM backend protocol.

Chunkers (pdf/text/detail) program against this interface instead of any
provider SDK, so the same file-processing machinery works for Gemini,
Claude, or anything implementing the protocol. Provider backends live in
``doc_curation.llm.gemini.backend`` and ``doc_curation.llm.claude.backend``.
"""
import abc
from typing import Any


class LlmChat(abc.ABC):
  """One stateful chat session (system prompt + model fixed at creation)."""

  @abc.abstractmethod
  def send_text(self, text: str) -> str:
    """Send a text message; return the model's output text."""

  @abc.abstractmethod
  def send_parts(self, parts: list) -> str:
    """Send a multi-part message (file refs mixed with text); return output text."""

  @abc.abstractmethod
  def last_metadata(self) -> dict:
    """Metadata of the most recent exchange ({} if none yet)."""


class LlmBackend(abc.ABC):
  """Factory for chats plus file upload and single-shot generation."""

  #: Used when callers don't specify a model.
  DEFAULT_MODEL: str = ""

  @abc.abstractmethod
  def new_chat(self, system_prompt: str, model_id: str | None = None) -> LlmChat:
    """Open a chat session; model_id=None selects DEFAULT_MODEL."""

  @abc.abstractmethod
  def upload_file(self, path: str) -> Any:
    """Upload a local file; returns an opaque ref for send_parts/generate_content."""

  @abc.abstractmethod
  def generate_content(self, contents: list, model_id: str | None = None) -> tuple[str, dict]:
    """Single-shot generation; returns (output text, raw metadata dict)."""
