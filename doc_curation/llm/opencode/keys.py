"""Opencode API key handling (opencode-go via the opencode CLI).

Secrets live in the shared TOML store (default table ``opencode``), in the
same shapes as every other provider: either a plain string or an inline
table (``{key = "...", status = ..., retry_after = ...}``). Status helpers
are shared (single source of truth; no import cycle since gemini.keys
never imports opencode.*).
"""
from curation_utils import creds

from doc_curation.llm.gemini.keys import _DEFAULT_TOKENS_PATH, _resolve_secret

# Matches the other backends (gemini 600s, claude 600s): a stall must
# always surface instead of hanging the run forever.
REQUEST_TIMEOUT = 600.0

_clients = {}


class OpencodeClient:
  """Resolved credentials for one opencode-go key (transport is the CLI)."""

  def __init__(self, api_key, api_key_path, cred_path):
    self.api_key = api_key
    self.api_key_path = api_key_path
    self.cred_path = cred_path

  def __repr__(self):
    return f"OpencodeClient({self.api_key_path})"


def get_client(api_key_path="opencode.vv_zen", cred_path=None):
  if cred_path is None:
    cred_path = _DEFAULT_TOKENS_PATH
  cache_key = (api_key_path, str(cred_path))
  if cache_key not in _clients:
    raw = creds.get_toml_value(path=cred_path, key=api_key_path)
    api_key = _resolve_secret(raw)
    if not api_key:
      # Fail fast: without an explicit secret the CLI would silently fall
      # back to the user's saved auth.json credentials, defeating rotation.
      raise ValueError(f"No Opencode API key found at {api_key_path} in {cred_path}")
    _clients[cache_key] = OpencodeClient(api_key=api_key, api_key_path=api_key_path,
                                     cred_path=cred_path)
  return _clients[cache_key]
