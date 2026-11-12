"""CLI: ``python -m doc_curation.llm.configurer [sync|symlinks|all]``."""

from __future__ import annotations

import sys

from doc_curation.llm.configurer import sync, symlinks

ACTIONS = ("sync", "symlinks", "all")


def main(argv: list[str] | None = None) -> int:
  argv = list(sys.argv[1:] if argv is None else argv)
  action = argv.pop(0) if argv and argv[0] in ACTIONS else "all"

  if action == "sync":
    return sync.main(argv)
  if action == "symlinks":
    return symlinks.main(argv)

  # `all` runs both, forwarding only the flags both subcommands accept.
  shared = [arg for arg in argv if arg == "--dry-run"]
  status = sync.main(shared)
  if status:
    return status
  return symlinks.main(shared + [arg for arg in argv if arg == "--prune"])


if __name__ == "__main__":
  raise SystemExit(main())
