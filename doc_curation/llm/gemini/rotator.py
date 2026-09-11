"""Key rotation and retry policy shared by all processors."""
import logging
import random
import time
from datetime import datetime, timedelta, timezone

from google.genai.errors import ServerError

from curation_utils import creds

from .detail_chunker import process_details
from .keys import (
    _DEFAULT_TOKENS_PATH,
    _MAX_QUOTA_WAIT,
    _get_retry_delay,
    _is_dead_credential_error,
    _key_usability,
    _mark_key_status,
    _quota_cooldown_seconds,
    _status_kind,
)
from .pdf_chunker import process_pdf_chunks
from .text_chunker import process_text_chunks


def _should_rotate_key(exc):
  """Quota/rate-limit errors are per-key: rotating to a fresh key helps.

  Model overload / transient 5xx (e.g. 503 UNAVAILABLE "high demand ...
  try again later") is global to the model: all keys hit the same
  overloaded backend, so backoff + retry the SAME key instead.
  """
  code = getattr(exc, "code", None)
  if code == 429:
    return True
  if code in (500, 502, 503, 504):
    return False

  status = str(getattr(exc, "status", "") or "").upper()
  if status == "RESOURCE_EXHAUSTED":
    return True
  if status in ("INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"):
    return False

  text = str(exc)
  text_lower = text.lower()
  if (
      "resource_exhausted" in text_lower
      or "quota" in text_lower
      or "rate limit" in text_lower
      or "retrydelay" in text_lower
      or "please retry in" in text_lower
      or "429" in text
  ):
    return True
  return False


def _is_retryable_gemini_error(exc):
  # 5xx are transient server-side failures - always retry (same key or rotated,
  # decided by _should_rotate_key).
  if isinstance(exc, ServerError):
    return True

  code = getattr(exc, "code", None)
  if code in (429, 500, 502, 503, 504):
    return True

  status = str(getattr(exc, "status", "") or "").upper()
  if status in ("RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"):
    return True

  text = str(exc)
  text_lower = text.lower()

  return (
      "resource_exhausted" in text_lower
      or "429" in text
      or "500" in text
      or "502" in text
      or "503" in text
      or "504" in text
      or "quota" in text_lower
      or "rate limit" in text_lower
      or "retrydelay" in text_lower
      or "internal" in text_lower
      or "unavailable" in text_lower
      or "deadline" in text_lower
      or "overloaded" in text_lower
      or "try again" in text_lower
      or "timeout" in text_lower
      or "timed out" in text_lower
      or "connection" in text_lower
      or "reset" in text_lower
      or "temporarily" in text_lower
  )


def _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked):
  """End-of-run error alert for dead credentials. Never raises (a reporting
  failure must not mask the run's own outcome). Statuses are recorded at
  ban time; this only informs."""
  if not dead_found:
    return
  skipped = [k for k in dead_found if k not in dead_marked]
  message = (
    f"Dead Gemini API credentials detected under {api_key_path}: "
    f"{', '.join(dead_found)}. "
  )
  if dead_marked:
    message += (
      f"Marked DEAD in {keys_file} (will be skipped from "
      f"now on): {', '.join(dead_marked)}. Please replace them with fresh keys. "
    )
  if skipped:
    message += f"NOT marked - edit {keys_file} manually: {', '.join(skipped)}. "
  logging.error(message.strip())


def _call_with_keys(
    func,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  keys_file = cred_path if cred_path is not None else _DEFAULT_TOKENS_PATH
  if cred_path is None:
    table = creds.get_toml_value(api_key_path)
  else:
    table = creds.get_toml_value(api_key_path, cred_path)
  if not isinstance(table, dict) or not table:
    raise ValueError(f"No API keys found in {api_key_path}")
  keys = list(table.keys())

  # Honor statuses recorded by earlier runs: DEAD keys never run; QUOTA
  # EXCEEDED keys run again once their cooldown has passed.
  now = datetime.now(timezone.utc)
  usable, flagged, cooling = [], {}, []
  for name in keys:
    ok, reason, retry_at = _key_usability(name, table.get(name), now)
    if _status_kind(table.get(name).get("status") if isinstance(table.get(name), dict) else None) is not None:
      flagged[name] = True
    if ok:
      usable.append(name)
    elif reason == "dead":
      logging.warning(f"Skipping dead key {api_key_path}.{name} (status set by an earlier run).")
    else:
      cooling.append((name, retry_at))
  if not usable and cooling:
    soonest_name, soonest_at = min(cooling, key=lambda item: item[1])
    wait = (soonest_at - datetime.now(timezone.utc)).total_seconds()
    if wait <= _MAX_QUOTA_WAIT:
      logging.warning(
        f"All keys cooling; sleeping {wait:.0f}s until {api_key_path}.{soonest_name} "
        f"may be reused.",
      )
      time.sleep(max(0, wait))
      now = datetime.now(timezone.utc)
      # Grace covers sub-second wobble; the fallback covers frozen clocks
      # and NTP jumps (worst case the key re-bans on immediate reuse).
      usable = [name for name, retry_at in cooling
                if now + timedelta(seconds=5) >= retry_at]
      if not usable:
        usable = [soonest_name]
      # flagged intentionally left intact: a subsequent success clears the
      # stale file status.
  if not usable:
    details = [f"{name} (dead)" for name in keys if name not in [c[0] for c in cooling]]
    details += [
      f"{name} (quota until {retry_at.strftime('%Y-%m-%dT%H:%M:%SZ')})"
      for name, retry_at in cooling
    ]
    raise RuntimeError(f"No usable Gemini API keys under {api_key_path}: {'; '.join(details)}")
  keys = usable

  i = random.randrange(len(keys))

  if max_attempts is None:
    max_attempts = len(keys)

  # Keys that hit quota exhaustion (429/RESOURCE_EXHAUSTED) or turn out
  # dead (401/403/auth failures) are banned for the rest of the run: their
  # quota won't recover mid-run and dead accounts won't revive, so never
  # rotate back into them. Statuses are persisted to the keys file so
  # future runs decide smartly; a flag is cleared when its key succeeds.
  banned = set()
  dead_found = []
  dead_marked = []

  for attempt in range(max_attempts):
    while keys[i % len(keys)] in banned:
      i += 1
      if len(banned) >= len(keys):
        _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
        raise RuntimeError(
          f"All {len(keys)} API keys banned for rest of run: {sorted(banned)}"
        )
    key_name = keys[i % len(keys)]
    key = f"{api_key_path}.{key_name}"

    for transient_attempt in range(max_transient_retries + 1):
      try:
        logging.info("Cred %s", key)

        result = func(
          *args,
          api_key_path=key,
          **kwargs,
        )
        if key_name in flagged:
          # The key works again: drop its stale status flag.
          try:
            if _mark_key_status(keys_file, api_key_path, key_name, None):
              logging.info(f"Cred {key} works again; cleared its status flag in {keys_file}.")
          except Exception as status_error:
            logging.warning(f"Could not clear status flag in {keys_file}: {status_error}")
        _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
        return result

      except Exception as e:
        if _is_dead_credential_error(e):
          # Dead credential (deleted/disabled account, invalid key, ...):
          # waiting cannot help, so ban immediately and rotate without
          # sleeping.
          banned.add(key_name)
          if key_name not in dead_found:
            dead_found.append(key_name)
          try:
            if _mark_key_status(keys_file, api_key_path, key_name, "DEAD"):
              if key_name not in dead_marked:
                dead_marked.append(key_name)
          except Exception as status_error:
            logging.warning(f"Could not record DEAD status in {keys_file}: {status_error}")
          logging.error(
            f"Cred {key} is dead, banning for rest of run and rotating: {e}",
          )
          if len(banned) >= len(keys):
            _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
            raise RuntimeError(
              f"All {len(keys)} API keys dead/banned for rest of run: {sorted(banned)}"
            )
          break

        if not _is_retryable_gemini_error(e):
          _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
          raise

        if _should_rotate_key(e):
          base_delay = min(2 ** attempt, 300)
          delay = _get_retry_delay(e, base_delay)
          banned.add(key_name)
          try:
            _mark_key_status(keys_file, api_key_path, key_name, "QUOTA EXCEEDED",
                             retry_after=_quota_cooldown_seconds(e))
          except Exception as status_error:
            logging.warning(f"Could not record quota status in {keys_file}: {status_error}")
          logging.warning(
            f"Cred {key} quota/rate-limit ({e}). "
            "Sleeping %.1fs, banning it for the rest of the run, and rotating.",
            delay,
          )
          time.sleep(delay)
          if len(banned) >= len(keys):
            _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
            raise RuntimeError(
              f"All {len(keys)} API keys banned for rest of run: {sorted(banned)}"
            )
          break

        # Model overload / transient 5xx / transport blip (e.g. 503
        # UNAVAILABLE "high demand ... try again later"): same backend for
        # every key, so backoff + retry the SAME key.
        if transient_attempt >= max_transient_retries:
          base_delay = min(2 ** attempt, 300)
          delay = _get_retry_delay(e, base_delay)
          logging.warning(
            f"Cred {key} overload persists after "
            f"{max_transient_retries + 1} same-key tries ({e}). "
            "Sleeping %.1fs and rotating as fallback.",
            delay,
          )
          time.sleep(delay)
          break

        base_delay = min(5 * (2 ** transient_attempt), 300)
        delay = _get_retry_delay(e, base_delay)
        # Small jitter so concurrent workers don't wake in lockstep.
        delay = delay + random.uniform(0, 1)
        logging.warning(
          f"Model overloaded/transient ({e}). "
          f"Sleeping {delay:.1f}s and retrying same key {key} "
          f"(try {transient_attempt + 2}/{max_transient_retries + 1}).",
        )
        time.sleep(delay)
        continue

    i += 1

  _report_dead_keys(keys_file, api_key_path, dead_found, dead_marked)
  raise RuntimeError(
    f"Failed after {max_attempts} attempts across {len(keys)} API keys"
  )


def process_pdf_chunks_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_pdf_chunks,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
  )


def process_text_chunks_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_text_chunks,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
  )


def process_details_with_keys(
    file_in,
    *args,
    api_key_path="gemini_friends",
    cred_path=None,
    max_attempts=None,
    max_transient_retries=8,
    **kwargs,
):
  return _call_with_keys(
    process_details,
    file_in,
    *args,
    api_key_path=api_key_path,
    cred_path=cred_path,
    max_attempts=max_attempts,
    max_transient_retries=max_transient_retries,
    **kwargs,
  )
