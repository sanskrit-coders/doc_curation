"""Helpers for reading LLM/agent session logs and producing readable transcripts.

Currently supports JetBrains Air ``.airsession`` archives (zip files containing
``manifest.json`` and ``events.jsonl``).
"""
import json
import logging
import os
import zipfile
from collections import defaultdict


def _load_airsession(session_path):
  """Return (manifest, events) from an .airsession archive or extracted directory."""
  if os.path.isdir(session_path):
    manifest_path = os.path.join(session_path, "manifest.json")
    events_path = os.path.join(session_path, "events.jsonl")
    with open(manifest_path, encoding="utf-8") as f:
      manifest = json.load(f)
    events = []
    with open(events_path, encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if line:
          events.append(json.loads(line))
    return manifest, events

  with zipfile.ZipFile(session_path) as zf:
    with zf.open("manifest.json") as f:
      manifest = json.load(f)
    events = []
    with zf.open("events.jsonl") as f:
      for raw_line in f:
        line = raw_line.decode("utf-8").strip()
        if line:
          events.append(json.loads(line))
  return manifest, events


def airsession_to_transcript(session_path, dest_path=None, include_user=False, include_tool_calls=False,
                             include_thoughts=True, include_agent=True):
  """Create a readable Markdown transcript from a JetBrains Air session log.

  :param session_path: Path to a ``.airsession`` zip archive, or an extracted directory
      containing ``manifest.json`` and ``events.jsonl``.
  :param dest_path: If given, write the transcript to this path.
  :param include_user: Include user messages.
  :param include_tool_calls: Include tool-call summaries (name/status/location), not outputs.
  :param include_thoughts: Include ``Runtime`` MessageChunk content (LLM thinking).
  :param include_agent: Include ``Agent`` MessageChunk content (visible agent messages).
  :return: Transcript text.
  """
  manifest, events = _load_airsession(session_path)

  user_msgs = {}
  chunks = defaultdict(list)  # turnId -> [(seq, role, delta)]
  tool_calls = {}
  turn_order = []
  seen_turns = set()

  for e in events:
    turn_id = e.get("turnId")
    if turn_id and turn_id not in seen_turns:
      seen_turns.add(turn_id)
      turn_order.append(turn_id)

    etype = e.get("type")
    payload = e.get("payload", {})
    if etype == "MessageDelta" and payload.get("role") == "User":
      mid = payload["messageId"]
      user_msgs.setdefault(mid, {"content": "", "attachments": [], "turnId": turn_id})
      user_msgs[mid]["content"] += payload.get("contentDelta", "")
      if payload.get("attachments"):
        user_msgs[mid]["attachments"] = payload["attachments"]
    elif etype == "MessageChunk":
      role = payload.get("role")
      if (role == "Runtime" and include_thoughts) or (role == "Agent" and include_agent):
        chunks[turn_id].append((e.get("seq", 0), role, payload.get("contentDelta", "")))
    elif etype == "ToolCallUpdated" and include_tool_calls:
      tcid = payload.get("toolCallId")
      if not tcid:
        continue
      if tcid not in tool_calls:
        tool_calls[tcid] = {
          "title": payload.get("title", ""),
          "kind": payload.get("kind", ""),
          "status": payload.get("status", ""),
          "seq": e.get("seq", 0),
          "turnId": turn_id,
          "locations": payload.get("locations", []) or [],
        }
      else:
        if payload.get("status"):
          tool_calls[tcid]["status"] = payload["status"]
        if payload.get("title"):
          tool_calls[tcid]["title"] = payload["title"]
        if payload.get("locations"):
          tool_calls[tcid]["locations"] = payload["locations"]

  lines = []
  title = manifest.get("title", "Air Session")
  lines.append(f"# {title}")
  lines.append("")
  lines.append(f"- **Source**: `{os.path.abspath(session_path)}`")
  project = manifest.get("projectPathPrefix", "")
  if project:
    lines.append(f"- **Project**: `{project}`")
  lines.append(f"- **Events**: {len(events)}")
  included = []
  if include_user:
    included.append("user messages")
  if include_thoughts:
    included.append("Runtime thinking")
  if include_agent:
    included.append("Agent messages")
  if include_tool_calls:
    included.append("tool-call summaries")
  lines.append(f"- **Included**: {', '.join(included) if included else 'nothing'}")
  lines.append("")

  for turn in turn_order:
    turn_user_msgs = [m for m in user_msgs.values() if m.get("turnId") == turn]
    turn_chunks = sorted(chunks.get(turn, []))
    turn_tool_calls = sorted((v["seq"], v) for v in tool_calls.values() if v.get("turnId") == turn)
    if not turn_user_msgs and not turn_chunks and not turn_tool_calls:
      continue

    lines.append(f"## Turn `{turn}`")
    lines.append("")

    if include_user:
      for msg in turn_user_msgs:
        lines.append("### User")
        lines.append("")
        lines.append(msg.get("content", ""))
        for attachment in msg.get("attachments", []):
          name = attachment.get("name", "Attachment")
          body = attachment.get("body", "")
          lines.append(f"\n> Attachment: {name} - {body}")
        lines.append("")

    if include_tool_calls and turn_tool_calls:
      lines.append("### Tool calls")
      for _, tc in turn_tool_calls:
        locations = tc.get("locations", []) or []
        loc = ""
        if locations:
          loc = " (" + ", ".join(l.get("path", "") for l in locations if l.get("path")) + ")"
        lines.append(f"- [{tc.get('status', '')}] {tc.get('kind', '')}: {tc.get('title', '')}{loc}".rstrip())
      lines.append("")

    cur_role = None
    buf = []

    def flush():
      if cur_role is None:
        return
      label = "Runtime thinking" if cur_role == "Runtime" else "Agent"
      lines.append(f"### {label}")
      lines.append("")
      lines.append("".join(buf))
      lines.append("")

    for _, role, delta in turn_chunks:
      if role != cur_role:
        flush()
        cur_role = role
        buf = [delta]
      else:
        buf.append(delta)
    flush()

  transcript = "\n".join(lines)
  if dest_path is not None:
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
      f.write(transcript)
    logging.info(f"Wrote transcript to {dest_path}")
  return transcript
