"""API key handling: clients, secrets, statuses, usability gating."""
import inspect
import logging
import os
from datetime import datetime, timedelta, timezone

import regex
from google import genai

from curation_utils import creds

_DEFAULT_TOKENS_PATH = inspect.signature(creds.get_toml_value).parameters["path"].default

# Silence verbose SDK trace and HTTP debug logs
for logger_name in ["google", "google.genai", "_trace", "httpx", "httpcore", "_client", "chats"]:
  logger = logging.getLogger(logger_name)
  logger.setLevel(logging.WARNING)
  logger.propagate = False

_clients = {}


def _resolve_secret(value):
  """Extract the API secret from plain-string or inline-table key entries.

  Supports both `name = "secret"` and `name = {key = "secret", ...}`.
  Anything else (including None) passes through unchanged.
  """
  if isinstance(value, dict):
    return value.get("key")
  return value


def get_client(api_key_path, cred_path="/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/tokens.toml"):
  # Cache per key-path so rotating api_key_path in
  # process_pdf_chunks_with_keys actually uses a different key.
  # (A single global client made rotation a no-op.)
  if api_key_path not in _clients:
    api_key = _resolve_secret(creds.get_toml_value(path=cred_path, key=api_key_path))
    _clients[api_key_path] = genai.Client(api_key=api_key)
  return _clients[api_key_path]


def _is_dead_credential_error(exc):
  """Detect deterministically-dead credentials (no retry or wait can help).

  E.g. 401 UNAUTHENTICATED "bound service account is deleted or disabled",
  400 API_KEY_INVALID, 403 PERMISSION_DENIED (key restrictions / API not
  enabled). These are per-key config states: ban the key and rotate.
  """
  code = getattr(exc, "code", None)
  if code in (401, 403):
    return True

  status = str(getattr(exc, "status", "") or "").upper()
  if status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
    return True

  text_lower = str(exc).lower()
  return (
      "api key not valid" in text_lower
      or "api_key_invalid" in text_lower
      or "account_state_invalid" in text_lower
      or "deleted or disabled" in text_lower
  )


_QUOTA_DEFAULT_COOLDOWN = 300


_MAX_QUOTA_WAIT = 600


def _utc_now_iso():
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_z(text):
  try:
    return datetime.strptime(str(text).strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
  except (ValueError, TypeError):
    return None


def _status_kind(status):
  """Classify a key status string: "dead", "quota", or None (usable)."""
  m = regex.match(r"^\s*(DEAD|QUOTA EXCEEDED)\b", str(status or ""), flags=regex.IGNORECASE)
  if not m:
    return None
  return "dead" if m.group(1).upper() == "DEAD" else "quota"


def _key_usability(name, entry, now):
  """Decide whether a key entry may be used: (usable, reason, retry_at).

  Plain strings are always usable. DEAD never is. QUOTA EXCEEDED is usable
  once its timestamp + retry_after has passed; unparseable timestamps fail
  open (with the in-run ban still protecting the run).
  """
  if not isinstance(entry, dict):
    return True, None, None
  kind = _status_kind(entry.get("status"))
  if kind is None:
    return True, None, None
  if kind == "dead":
    return False, "dead", None
  m = regex.match(r"^\s*QUOTA EXCEEDED\s*-\s*(\S+)\s*$", str(entry.get("status") or ""),
                  flags=regex.IGNORECASE)
  stamped_at = _parse_iso_z(m.group(1)) if m else None
  if stamped_at is None:
    logging.warning(f"Key {name} has an unparseable quota status; treating as usable.")
    return True, None, None
  try:
    retry_after = int(entry.get("retry_after", _QUOTA_DEFAULT_COOLDOWN))
  except (ValueError, TypeError):
    retry_after = _QUOTA_DEFAULT_COOLDOWN
  retry_at = stamped_at + timedelta(seconds=max(0, retry_after))
  if now >= retry_at:
    return True, None, None
  return False, "quota-cooling", retry_at


def _get_retry_delay(exc, default_delay):
  """
  Extract Gemini retryDelay from exception text, e.g.

      'retryDelay': '27s'

  Falls back to the exponential backoff delay.
  """
  text = str(exc)

  match = regex.search(r"'retryDelay':\s*'(\d+)s'", text)
  if match:
    return int(match.group(1))

  match = regex.search(r"Please retry in ([\d.]+)s", text)
  if match:
    return float(match.group(1))

  return default_delay


def _quota_cooldown_seconds(exc):
  """How long a fresh quota ban should keep the key out of rotation.

  Per-day quotas need ~a day (their short retryDelay notwithstanding);
  otherwise honor the error's retryDelay, defaulting conservatively.
  """
  text = str(exc)
  if regex.search(r"per[-_]?day", text, flags=regex.IGNORECASE):
    return 86400
  delay = _get_retry_delay(exc, None)
  if delay is None:
    return _QUOTA_DEFAULT_COOLDOWN
  return max(1, int(delay))


def _mark_key_status(keys_file, table_path, key_name, status, retry_after=None):
  """Record a key status in the keys file; True if the file changed.

  Rewrites `name = "secret"` (or an existing inline table) as single-line
  `name = {key = "secret", status = "<STATUS> - <ISO-UTC>"[, retry_after = N]}`
  (single-line: multiline inline tables are invalid TOML 1.0). status=None
  clears the flag back to `{key = "secret"}`. Only touches uncommented
  entries in the target table; multiline values, tables and arrays are left
  alone. Writes atomically.
  """
  with open(keys_file, "r", encoding="utf-8") as f:
    parts = f.read().split("\n")
  orig_mode = os.stat(keys_file).st_mode & 0o777
  target = tuple(table_path.split("."))
  current = None
  changed = False
  out = []
  for line in parts:
    header = regex.match(r"^[ \t]*\[([^\[\]]+)\][ \t]*$", line)
    if header:
      inner = header.group(1).strip()
      if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in ("\"", "'"):
        current = (inner[1:-1],)
      else:
        current = tuple(part.strip() for part in inner.split("."))
      out.append(line)
      continue
    if current == target and not line.strip().startswith("#"):
      m = regex.match(r"^(\s*)" + regex.escape(key_name) + r"\s*=\s*(.*)$",
                      line, flags=regex.DOTALL)
      if m:
        indent, value = m.group(1), m.group(2).strip()
        secret, trailing = None, ""
        strm = regex.match(r"""^(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')(.*)$""",
                           value, flags=regex.DOTALL)
        if strm:
          secret, trailing = strm.group(1), strm.group(2)
        else:
          inm = regex.match(r"^(\{.*\})(.*)$", value, flags=regex.DOTALL)
          if inm:
            keym = regex.search(r"""\bkey\s*=\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')""",
                                inm.group(1))
            if keym:
              secret, trailing = keym.group(1), inm.group(2)
        if secret is not None and (not trailing.strip() or trailing.strip().startswith("#")):
          fields = [f"key = {secret}"]
          if status is not None:
            fields.append(f"status = \"{status} - {_utc_now_iso()}\"")
            if retry_after is not None:
              fields.append(f"retry_after = {int(retry_after)}")
          out.append(f"{indent}{key_name} = {{{', '.join(fields)}}}{trailing}")
          changed = True
          continue
    out.append(line)
  if not changed:
    return False
  tmp_path = str(keys_file) + ".tmp"
  with open(tmp_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
  os.replace(tmp_path, keys_file)
  os.chmod(keys_file, orig_mode)
  return True
