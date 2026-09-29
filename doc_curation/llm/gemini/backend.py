"""Gemini backend implementing the shared LLM protocol."""
from google.genai import types

from doc_curation.llm.backend import LlmBackend, LlmChat

from .keys import get_client


class GeminiChat(LlmChat):
  def __init__(self, client, system_prompt, model_id):
    config = types.GenerateContentConfig(system_instruction=system_prompt)
    self._chat = client.chats.create(model=model_id, config=config)
    self._last_response = None

  def send_text(self, text):
    response = self._chat.send_message(text)
    self._last_response = response
    return response.text or ""

  def send_parts(self, parts):
    response = self._chat.send_message(parts)
    self._last_response = response
    return response.text or ""

  def last_metadata(self):
    if self._last_response is None:
      return {}
    return self._last_response.model_dump()


class GeminiBackend(LlmBackend):
  DEFAULT_MODEL = "gemini-3.5-flash"

  def __init__(self, api_key_path="gemini.vv", model_id=None, cred_path=None):
    self.api_key_path = api_key_path
    self.model = model_id or self.DEFAULT_MODEL
    self.cred_path = cred_path

  @property
  def client(self):
    return get_client(api_key_path=self.api_key_path, cred_path=self.cred_path)

  def new_chat(self, system_prompt, model_id=None):
    return GeminiChat(self.client, system_prompt, model_id or self.model)

  def upload_file(self, path):
    return self.client.files.upload(file=path)

  def generate_content(self, contents, model_id=None):
    response = self.client.models.generate_content(
      model=model_id or self.model,
      contents=contents,
    )
    return response.text or "", response.model_dump()
