"""Sanskrit proofreader, sandhi-hyphenator, interleaver & padapāṭha LLM toolkit."""
from .backend import ProofreaderBackend, ProofreaderChat, proofread_text
from .block_splitter import (
  group_sense_unit_blocks,
  has_genuine_iti,
  split_into_danda_segments,
  text_to_vipra_mula_blocks,
)
from .guards import (
  canonical_sandhi_skeleton,
  enforce_post_guards,
  mask_protected_blocks,
  rejoin_merger_violations,
  restore_protected_blocks,
  wrap_silent_mutations,
)
from .interleave_aligner import align_commentary_segments, refine_interleave_plan
from .interleave_helper import interleave_source_into_markdown, verify_interleaved_markdown
from .kaggle_jobs.kaggle_runner import DEFAULT_LOCAL_ADAPTER_DIR, save_adapter_locally
from .prompts import (
  INTERLEAVER_SYSTEM_PROMPT,
  PADAPATHA_ACCENT_SYSTEM_PROMPT,
  build_system_prompt,
)
from .translation_aligner import (
  align_cores_to_translation_dp,
  local_translation_generate_fn,
  refine_translation_mapping,
)

__all__ = [
  "DEFAULT_LOCAL_ADAPTER_DIR",
  "INTERLEAVER_SYSTEM_PROMPT",
  "PADAPATHA_ACCENT_SYSTEM_PROMPT",
  "ProofreaderBackend",
  "ProofreaderChat",
  "align_commentary_segments",
  "align_cores_to_translation_dp",
  "build_system_prompt",
  "canonical_sandhi_skeleton",
  "enforce_post_guards",
  "group_sense_unit_blocks",
  "has_genuine_iti",
  "interleave_source_into_markdown",
  "local_translation_generate_fn",
  "mask_protected_blocks",
  "proofread_text",
  "refine_interleave_plan",
  "refine_translation_mapping",
  "rejoin_merger_violations",
  "restore_protected_blocks",
  "save_adapter_locally",
  "split_into_danda_segments",
  "text_to_vipra_mula_blocks",
  "verify_interleaved_markdown",
  "wrap_silent_mutations",
]
