<!-- Batch-prompt template for translation_matcher._prompt_for_batch.
This file is the prompt's source of truth: edit the prose here, no code
changes needed (it is re-read on every LLM call).

The translation is given UNSPLIT as plain text ($en_words). The model
splits it by regex \s itself, numbers the resulting strings 0-based,
and reports spans as indices into its own split — verified against
$e_window_count, so no per-word numbering inflates the prompt. The
model does NOT know where the relevant translation ends: it maps only
what genuinely renders these cores and stops, leaving any tail
unmatched (expected and reported, never an error).

Placeholders ($-style, string.Template): $total_core_m1, $total_core,
$total_en_m1, $total_en, $c_start, $c_last, $e_start (global offset of
this window, context only — indices below are window-relative),
$e_window_count, $anchor (continuity block or empty), $pacing (pacing
block, always), $core_lines, $en_words, $upcoming (next batch's cores
as read-only context, or empty on the last batch). A literal $ must be
written $$. This leading HTML comment is stripped before use, as is one
trailing newline. -->

Align the core texts below, IN ORDER, with the translation words below. Core texts 0..$total_core_m1 map into a prefix of the provided translation stream. This continues a longer alignment: everything before core $c_start is already fixed, and the translation text below starts at global word $e_start.  

The translation is one unsplit text — split it yourself by regex \s (whitespace runs) into strings, number them 0-based, and match each core text to its strings in the order they appear: The text below holds exactly $e_window_count strings — verify SILENTLY that your split yields that many (narrate nothing; reply with ONLY the JSON below).

Read each core text, find where its English rendering begins, and continue from there. Note that there may be extra content at the end (e.g., commentary text with no matching Sanskrit). That should be reported using next_en as specified below.

$anchor$pacing
RULES:
- Partition, no gaps, no overlaps: the spans of the taken cores tile strings 0..next_en of your split in order (core i's span runs up to the next core's start; the last taken core's span runs up to next_en). Spans may start and end INSIDE sentences — at clause boundaries, pivots like '--But, it may be said…', wherever the content breaks. Indices below are positions in YOUR split (0-based); the code converts them to stream positions.
- You do NOT know beforehand where the relevant translation for the core text ends, and you must NOT attempt to match everything: map only what genuinely renders these cores. When the translation text moves on to later material (beyond the core text), STOP — set next_en there and leave the rest unmatched. UPCOMING CORES, if provided, may help you determine next_en. Unmatched tail is expected and reported, never an error. Do not stretch takes or invent matches to consume text.
- Every core EITHER takes at least one translation string OR is named in "skip". A core with an empty span that is NOT in "skip" is invalid.
- Skip ONLY cores with NO sequentially separable strings rendering them: colophons like 'इति ...', bare interjections ('किं युक्तम्?', 'कुतः?'), or passages the translation demonstrably omits. Dumping hard sentences into "skip" to avoid reading them is the failure mode to avoid: place each core deliberately against the window.

CORE TEXTS:
$core_lines

TRANSLATION WORDS:
$en_words

$upcoming

Reply with ONLY this JSON (no prose, no fences needed but fences allowed):
{"starts": {"$c_start": 0, ...}, "skip": [], "next_en": <int>}
- "starts" must contain exactly the core indices $c_start..$c_last, each mapping to the FIRST string of its span in your split (integer in [0, $e_window_count]).
- Starts must be non-decreasing; the first start must equal 0.
- "skip": core indices (subset of the batch) whose span is EMPTY — i.e. their start repeats the next boundary, consuming nothing. Use only for the genuine no-rendering cases above.
- "next_en" is the first index AFTER this batch's last span in your split (integer in [last start, $e_window_count]); it may stop well before the window end (see the end-of-scope rule above).
