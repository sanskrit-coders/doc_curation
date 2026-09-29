"""Claude backend implementing the shared LLM protocol."""
import base64

from doc_curation.llm.backend import LlmBackend, LlmChat

from .keys import get_client


def _response_text(response):
  return "".join(
    getattr(block, "text", "") or ""
    for block in (getattr(response, "content", None) or [])
    if getattr(block, "type", "") == "text"
  )


def _response_metadata(response, model):
  usage = getattr(response, "usage", None)
  metadata = {
    "model": getattr(response, "model", model),
    "id": getattr(response, "id", None),
    "stop_reason": getattr(response, "stop_reason", None),
  }
  if usage is not None:
    metadata["usage"] = {
      "input_tokens": getattr(usage, "input_tokens", None),
      "output_tokens": getattr(usage, "output_tokens", None),
    }
  return metadata


def _as_content_block(part):
  if isinstance(part, dict):
    return part
  return {"type": "text", "text": str(part)}


class ClaudeChat(LlmChat):
  def __init__(self, client, system_prompt, model, max_tokens):
    self._client = client
    self._system = system_prompt or None
    self._model = model
    self._max_tokens = max_tokens
    self._messages = []
    self._metadata = {}

  def _call(self, content):
    if isinstance(content, list):
      blocks = [_as_content_block(part) for part in content]
    else:
      blocks = content
    self._messages.append({"role": "user", "content": blocks})
    kwargs = {}
    if self._system:
      kwargs["system"] = self._system
    response = self._client.messages.create(
      model=self._model, max_tokens=self._max_tokens,
      messages=self._messages, **kwargs)
    text = _response_text(response)
    self._metadata = _response_metadata(response, self._model)
    self._messages.append({"role": "assistant", "content": text})
    return text

  def send_text(self, text):
    return self._call(text)

  def send_parts(self, parts):
    return self._call(parts)

  def last_metadata(self):
    return dict(self._metadata)


class ClaudeBackend(LlmBackend):
  DEFAULT_MODEL = "claude-sonnet-4-5"
  DEFAULT_MAX_TOKENS = 8192

  def __init__(self, api_key_path="claude.default", model_id=None, max_tokens=None, cred_path=None):
    self.api_key_path = api_key_path
    self.model = model_id or self.DEFAULT_MODEL
    self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
    self.cred_path = cred_path

  @property
  def client(self):
    return get_client(api_key_path=self.api_key_path, cred_path=self.cred_path)

  def new_chat(self, system_prompt, model_id=None):
    return ClaudeChat(self.client, system_prompt, model_id or self.model, self.max_tokens)

  def upload_file(self, path):
    # Native PDF support via base64 document block (no Files API needed).
    with open(path, "rb") as f:
      data = base64.b64encode(f.read()).decode("ascii")
    return {"type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data}}

  def generate_content(self, contents, model_id=None):
    model = model_id or self.model
    response = self.client.messages.create(
      model=model, max_tokens=self.max_tokens,
      messages=[{"role": "user",
                 "content": [_as_content_block(part) for part in contents]}])
    return _response_text(response), _response_metadata(response, model)
