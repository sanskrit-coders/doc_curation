"""Opencode backend implementing the shared LLM protocol.

Muse Spark is reached through the ``opencode`` CLI (``opencode run`` with
``-m opencode-go/muse-spark-...``), not an SDK. Each backend instance owns
an isolated ``XDG_DATA_HOME`` directory so that:

* the per-key secret from tokens.toml is the *only* credential visible
  (via ``OPENCODE_API_KEY``), giving real per-key rotation instead of
  silently sharing the user's saved auth.json, and
* chat sessions (``opencode run -s <id>``) persist within the backend
  without touching the user's main opencode database.

File attachments are staged under ``/tmp/opencode/`` (allowlisted for
reads in the default agent config); other locations get auto-rejected.
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile

import regex

from doc_curation.llm.backend import LlmBackend, LlmChat

from .keys import REQUEST_TIMEOUT, get_client

# Staging + per-backend data-homes live here: the default agent config
# allowlists reads under /tmp/opencode/* (other paths are auto-rejected).
UPLOAD_BASE = "/tmp/opencode"


class OpencodeError(Exception):
  """A failed ``opencode run`` invocation, classified for the rotator."""

  def __init__(self, message, status_code=None, code=None, rotate_without_persist=False):
    super().__init__(message)
    self.status_code = status_code
    self.code = code
    # Workspace-policy blocks (e.g. training-on-data models disabled):
    # rotate to another key for this run, but do NOT persist any status
    # (the key itself is fine, possibly for other models).
    self.rotate_without_persist = rotate_without_persist


class OpencodeTimeoutError(OpencodeError, TimeoutError):
  """The CLI call itself stalled past its timeout (name-matched retryable)."""


class OpencodeFileRef(str):
  """A staged attachment path, distinguishable from plain message text."""


def _is_policy_block(text):
  """Workspace-policy refusal (key usable in principle, not for this model)."""
  return bool(regex.search(
    r"trains on request data|privacy settings|permission denied|not allowed|forbidden|not enabled",
    text, flags=regex.IGNORECASE))


def _classify_output(text):
  """Best-effort HTTP-ish status code from CLI output text (or None)."""
  if regex.search(r"invalid credential", text, flags=regex.IGNORECASE):
    return 401
  m = regex.search(r"error\s*code\s*[:=]\s*(\d{3})", text, flags=regex.IGNORECASE)
  if m:
    return int(m.group(1))
  m = regex.search(r"status(?:\s*code)?\s*[:=]\s*(\d{3})", text, flags=regex.IGNORECASE)
  if m:
    return int(m.group(1))
  lowered = text.lower()
  if "rate limit" in lowered or "rate_limit" in lowered or "too many requests" in lowered:
    return 429
  if "overloaded" in lowered:
    return 529
  if "unavailable" in lowered:
    return 503
  return None


def _sniff_log(data_home):
  """Last-resort hint from the isolated opencode log (timeouts leave stdout empty)."""
  log_path = os.path.join(data_home, "opencode", "log", "opencode.log")
  try:
    with open(log_path, encoding="utf-8", errors="replace") as f:
      lines = f.read().splitlines()[-40:]
  except OSError:
    return ""
  for line in reversed(lines):
    if "Invalid credential" in line:
      return "Log tail reports: Invalid credential."
    m = regex.search(r"(429|401|403|500|502|503|504|529|rate.?limit|overloaded|quota)", line,
                     flags=regex.IGNORECASE)
    if m:
      return f"Log tail reports: {line.strip()[-200:]}"
  return ""


def _run_opencode(*, api_key, data_home, model, message, files, session_id, timeout, variant=None):
  """One ``opencode run`` call; returns (text, metadata). Raises OpencodeError."""
  if shutil.which("opencode") is None:
    raise OpencodeError("opencode binary not found on PATH")
  cmd = ["opencode", "run", "-m", model, "--format", "json"]
  if variant:
    cmd += ["--variant", variant]
  if session_id:
    cmd += ["-s", session_id]
  # NOTE: message must precede -f flags; -f greedily consumes following args.
  cmd += [message]
  for f in files:
    cmd += ["-f", f]
  env = dict(os.environ)
  env["OPENCODE_API_KEY"] = api_key
  env["XDG_DATA_HOME"] = data_home
  try:
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL, env=env)
  except subprocess.TimeoutExpired as e:
    hint = _sniff_log(data_home)
    raise OpencodeTimeoutError(
      f"opencode run timed out after {timeout:g}s (model {model}). {hint}".strip()
    ) from e
  texts, session, tokens, cost = [], None, {}, 0.0
  err_texts, err_code = [], None
  stdout_tail = []
  for line in (proc.stdout or "").splitlines():
    line = line.strip()
    if not line:
      continue
    stdout_tail.append(line[-200:])
    try:
      evt = json.loads(line)
    except ValueError:
      logging.debug("opencode non-JSON stdout line: %s", line[:200])
      continue
    if not isinstance(evt, dict):
      continue
    sid = evt.get("sessionID")
    if sid:
      session = sid
    if evt.get("type") == "text":
      part = evt.get("part") or {}
      text = part.get("text")
      if text:
        texts.append(text)
    elif evt.get("type") == "step_finish":
      part = evt.get("part") or {}
      if part.get("tokens"):
        tokens = part["tokens"]
      if part.get("cost") is not None:
        cost = part["cost"]
    elif evt.get("type") == "error":
      err = evt.get("error") or {}
      data = err.get("data") or {}
      if err.get("message"):
        err_texts.append(str(err["message"]))
      if data.get("message"):
        err_texts.append(str(data["message"]))
      for key in ("statusCode", "status", "code"):
        if isinstance(data.get(key), int):
          err_code = data[key]
          break
  if proc.returncode != 0 or not texts:
    reasoning = tokens.get("reasoning", 0) if isinstance(tokens, dict) else 0
    output = tokens.get("output", 0) if isinstance(tokens, dict) else 0
    if proc.returncode == 0 and not err_texts and reasoning and not output:
      # The model thought itself silent: a reasoning model can burn its
      # whole output-token budget on chain-of-thought and emit nothing.
      # Retrying the same way won't help; steer the caller instead.
      raise OpencodeError(
        f"opencode run produced no answer: model {model} spent its entire token "
        f"budget on reasoning ({reasoning} reasoning tokens, 0 output) and never "
        f"emitted text. Use a lower reasoning effort (variant=), a non-reasoning "
        f"model, or smaller chunks/batches. session {session}.",
        status_code=None,
      )
    blob = "\n".join([*err_texts, proc.stderr or "", *stdout_tail[-10:], _sniff_log(data_home)])
    code = err_code if err_code is not None else _classify_output(blob)
    detail = "failed (exit %d)" % proc.returncode if proc.returncode != 0 else "produced no text"
    raise OpencodeError(
      f"opencode run {detail} (model {model}, session {session}): "
      f"{blob.strip()[-1500:]}",
      status_code=code,
      rotate_without_persist=bool(err_texts) and code == 400 and _is_policy_block(blob),
    )
  metadata = {"model": model, "session": session, "tokens": tokens, "cost": cost}
  return "".join(texts), metadata


class OpencodeChat(LlmChat):
  def __init__(self, api_key, data_home, system_prompt, model, timeout, variant=None):
    self._api_key = api_key
    self._data_home = data_home
    self._system = system_prompt
    self._model = model
    self._timeout = timeout
    self._variant = variant
    self._session_id = None
    self._metadata = {}
    self._first = True

  def _send(self, message, files):
    if self._first and self._system:
      message = f"{self._system}\n\n{message}"
    self._first = False
    text, metadata = _run_opencode(
      api_key=self._api_key, data_home=self._data_home, model=self._model,
      message=message, files=files, session_id=self._session_id,
      timeout=self._timeout, variant=self._variant)
    if metadata.get("session"):
      self._session_id = metadata["session"]
    self._metadata = metadata
    return text

  def send_text(self, text):
    return self._send(text, [])

  def send_parts(self, parts):
    files = [str(p) for p in parts if isinstance(p, OpencodeFileRef)]
    texts = [str(p) for p in parts if not isinstance(p, OpencodeFileRef)]
    return self._send("\n\n".join(texts), files)

  def last_metadata(self):
    return dict(self._metadata)


class OpencodeBackend(LlmBackend):
  DEFAULT_MODEL = "opencode-go/muse-spark-1.3-contributor"
  PROVIDER_TAG = "Opencode"

  def __init__(self, api_key_path="opencode.vv_zen", model_id=None, cred_path=None,
               timeout=REQUEST_TIMEOUT, variant=None):
    self.api_key_path = api_key_path
    self.model = self._normalize_model(model_id)
    self.cred_path = cred_path
    self.timeout = timeout
    # Provider-specific reasoning effort (e.g. "minimal", "high", "max").
    # Useful for reasoning models that overspend their token budget.
    self.variant = variant
    os.makedirs(UPLOAD_BASE, exist_ok=True)
    # Isolated auth/session state for this backend instance.
    self._data_home = tempfile.mkdtemp(prefix="opencode-", dir=UPLOAD_BASE)
    self._upload_seq = 0

  @staticmethod
  def _normalize_model(model_id):
    if not model_id:
      return OpencodeBackend.DEFAULT_MODEL
    if "/" not in model_id:
      return f"opencode-go/{model_id}"
    return model_id

  @property
  def client(self):
    return get_client(api_key_path=self.api_key_path, cred_path=self.cred_path)

  def new_chat(self, system_prompt, model_id=None):
    return OpencodeChat(self.client.api_key, self._data_home, system_prompt,
                        model_id or self.model, self.timeout, self.variant)

  def upload_file(self, path):
    # Stage a copy under the allowlisted base: the caller's temp file may
    # live anywhere (rejected locations) and may be deleted right after.
    if not os.path.isfile(path):
      raise OpencodeError(f"Cannot attach missing file: {path}")
    staged_dir = os.path.join(self._data_home, "uploads")
    os.makedirs(staged_dir, exist_ok=True)
    self._upload_seq += 1
    staged = os.path.join(staged_dir, f"{self._upload_seq:04d}_{os.path.basename(path)}")
    shutil.copyfile(path, staged)
    return OpencodeFileRef(staged)

  def generate_content(self, contents, model_id=None):
    model = model_id or self.model
    files = [str(p) for p in contents if isinstance(p, OpencodeFileRef)]
    texts = [str(p) for p in contents if not isinstance(p, OpencodeFileRef)]
    text, metadata = _run_opencode(
      api_key=self.client.api_key, data_home=self._data_home, model=model,
      message="\n\n".join(texts), files=files, session_id=None,
      timeout=self.timeout, variant=self.variant)
    return text, metadata
