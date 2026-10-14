<!-- Batch-prompt template for translation_matcher._prompt_for_batch.
This file is the prompt's source of truth: edit the prose here, no code
changes needed (it is re-read on every LLM call).

Placeholders ($-style, string.Template): $total_core_m1, $total_core,
$total_en_m1, $total_en, $c_start, $c_last, $e_start, $e_window_end,
$anchor (continuity block or empty), $pacing (pacing block, always),
$core_lines, $en_lines. A literal $ must be written $$. This leading
HTML comment is stripped before use, as is one trailing newline. -->

Align the core texts below, IN ORDER, with the translation sentences below. This continues a longer alignment: core texts 0..$total_core_m1 map into translation sentences 0..$total_en_m1; everything before core $c_start / sentence $e_start is already fixed. Match the translation sentences to the cores in the order they appear: read each core text, find where its English rendering begins, and continue from there.
$anchor$pacing
RULES:
- Partition, no gaps, no overlaps: the spans of the taken cores tile translation sentences $e_start..next_en in order (core i's span runs up to the next core's start; the last taken core's span runs up to next_en). You may stop (next_en) before the window end; leftover sentences carry over to the next batch.
- Every core EITHER takes at least one translation sentence OR is named in "skip". A core with an empty span that is NOT in "skip" is invalid.
- PIVOT SENTENCES: the translator often pivots mid-sentence to the next point ('--But, it may be said…', '--Now…', '--And…', 'it may be objected…'). Such a unit's HEAD renders the current core while its TAIL already renders the NEXT core — assigning it to either core alone buries half of it. When you see one, name the next core in "carry": the pivot unit then displays above that core's own take as well (verbatim, under both). Use carry ONLY for genuine pivots — never to duplicate ordinary units.
- Skip ONLY cores with genuinely no English counterpart here: colophons like 'इति ...', verse fragments whose content a neighbouring core's span already covers (in a way that it can't be sequentially split), or passages the translation demonstrably does not render. Dumping hard sentences into "skip" to avoid reading them is the failure mode to avoid: place each core deliberately against the window.

CORE TEXTS:
$core_lines

TRANSLATION SENTENCES:
$en_lines

Reply with ONLY this JSON (no prose, no fences needed but fences allowed):
{"starts": {"$c_start": $e_start, ...}, "skip": [], "carry": [], "next_en": <int>}
- "starts" must contain exactly the core indices $c_start..$c_last, each mapping to the FIRST translation sentence of its span (integer in [$e_start, $e_window_end]).
- Starts must be non-decreasing; the first start must equal $e_start.
- "skip": core indices (subset of the batch) whose span is EMPTY — i.e. their start repeats the next boundary, consuming nothing. Use only for the genuine no-counterpart cases above.
- "carry": core indices (subset of the batch, disjoint from "skip") that additionally display the immediately preceding unit — pivot tails only. Each carried core's start must be at least 1 (unit 0 has no predecessor to show; the carried unit is always visible to you: either inside this window or as the anchor above).
- "next_en" is the first translation index AFTER this batch's last span (integer in [last start, $e_window_end]).
