"""Claude API key handling (Anthropic clients)."""
import anthropic

from curation_utils import creds

# Shared keystore infra (single source of truth; no import cycle since
# gemini.keys never imports claude.*).
from doc_curation.llm.gemini.keys import _DEFAULT_TOKENS_PATH, _resolve_secret

# Matches the SDK default, stated explicitly so a stall always surfaces
# (see gemini.keys.get_client for why an unbounded wait is dangerous).
REQUEST_TIMEOUT = 600.0

_clients = {}


def get_client(api_key_path="claude.default", cred_path=None):
  if cred_path is None:
    cred_path = _DEFAULT_TOKENS_PATH
  cache_key = (api_key_path, str(cred_path))
  if cache_key not in _clients:
    raw = creds.get_toml_value(path=cred_path, key=api_key_path)
    _clients[cache_key] = anthropic.Anthropic(api_key=_resolve_secret(raw), timeout=REQUEST_TIMEOUT)
  return _clients[cache_key]
