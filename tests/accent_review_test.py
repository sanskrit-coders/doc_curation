import os
import re
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from doc_curation.sanskrit.accent import reconciler, review, review_gui, validator


def _git(cwd: Path, *args: str) -> str:
  return subprocess.check_output(["git", "-C", str(cwd), *args], text=True)


def _init_git_repo(repo_dir: Path) -> None:
  repo_dir.mkdir(parents=True, exist_ok=True)
  _git(repo_dir, "init")
  _git(repo_dir, "config", "user.name", "Test Reviewer")
  _git(repo_dir, "config", "user.email", "reviewer@example.org")


def test_feedback_comment_formatting_and_extraction():
  assert review.format_feedback_comment("") == ""
  assert review.format_feedback_comment("   ") == ""
  assert review.format_feedback_comment("Are you sure?") == "+++(Are you sure?!!)+++"
  assert review.format_feedback_comment("Are you sure?!!") == "+++(Are you sure?!!)+++"
  assert review.format_feedback_comment("+++(Are you sure?!!)+++") == "+++(Are you sure?!!)+++"
  assert review.format_feedback_comment("Check (MW)") == "+++(Check (MW)!!)+++"
  assert review.extract_feedback_inner(" +++(Are you sure?!!)+++") == "Are you sure?!!"
  assert review.extract_feedback_inner(" +++(Check (MW)!!)+++") == "Check (MW)!!"


def test_scan_inline_context_window_and_feedback_insertion(tmp_path: Path):
  cache_dir = str(tmp_path / "cache")
  content_dir = tmp_path / "vedAH_yajuH" / "content" / "maitrAyaNIyam" / "saMhitA" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)
  md_file = content_dir / "01.md"

  aranya_pp = "- अ᳓रण्या → **अर᳓ण्या** (*TS*-0/2, *RV*-0/6, *TB*-0/1, *AV*-0/1, *SB-M*-0/14, *SB-K*-0/11, *MS*-0/2, प्रातिपदिकम् अर᳓णि/अर᳓णी (*MW*))"
  md_file.write_text(
    "+++\ntitle = \"01\"\n+++\n\n"
    "## मन्त्रः १\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "इमा᳓म् **[[अ᳓रण्या|अर᳓ण्या]]** ते᳓जसा\n\n"
    "</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/5 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- इमा᳓म् (*TS*-14, *RV*-20)\n"
    "- ते᳓जसा (*TS*-5, *RV*-3)\n"
    f"{aranya_pp}\n"
    "- देवाः᳓ (*TS*-40, *RV*-60)\n"
    "- नमः᳓ (*TS*-99, *RV*-80)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  scan = review.scan_directory(str(content_dir))
  assert len(scan["items"]) == 1
  item = scan["items"][0]
  assert item.kind == "both"
  assert item.vp_sug_old == "अ᳓रण्या"
  assert item.vp_sug_new == "अर᳓ण्या"
  assert len(item.vp_highlight_ranges) == 1
  s, e = item.vp_highlight_ranges[0]
  assert "[[अ᳓रण्या|अर᳓ण्या]]" in item.vp_raw_body[s:e]

  d0 = item.to_dict(n_context=0)
  assert d0["pp_context_before"] == []
  assert d0["pp_target_line"] == aranya_pp
  assert d0["pp_context_after"] == []

  d1 = item.to_dict(n_context=1)
  assert d1["pp_context_before"] == ["- ते᳓जसा (*TS*-5, *RV*-3)"]
  assert d1["pp_target_line"] == aranya_pp
  assert d1["pp_context_after"] == ["- देवाः᳓ (*TS*-40, *RV*-60)"]

  d3 = item.to_dict(n_context=3)
  assert len(d3["pp_context_before"]) == 2
  assert len(d3["pp_context_after"]) == 2

  res = review.insert_feedback_for_item(item, "Are you sure?", scan_dir=str(content_dir))
  expected_line = f"{aranya_pp} +++(Are you sure?!!)+++"
  assert res["pp_target_line"] == expected_line
  assert item.existing_feedback == "Are you sure?!!"
  assert expected_line in md_file.read_text(encoding="utf-8")

  # Confirm the updated पद-पाठः block still parses cleanly and passes validator checks
  pp_blocks = [
    m for m in reconciler.LEAF_DETAILS_RE.finditer(md_file.read_text(encoding="utf-8"))
    if m.group(1).strip().startswith("पद-पाठः")
  ]
  assert len(pp_blocks) == 1
  parsed = reconciler.parse_padapatha_items(pp_blocks[0].group(2).strip())
  assert len(parsed) == 5
  assert parsed[2].vyat is True and parsed[2].ar == "अ᳓रण्या" and parsed[2].ref == "अर᳓ण्या"
  assert validator.validate_padapatha_block(pp_blocks[0].group(1).strip(), pp_blocks[0].group(2).strip()) == []

  # Updating and clearing feedback works cleanly without duplicating markers
  review.insert_feedback_for_item(item, "Check RV accent too!!", scan_dir=str(content_dir))
  txt2 = md_file.read_text(encoding="utf-8")
  assert f"{aranya_pp} +++(Check RV accent too!!)+++" in txt2
  assert "Are you sure" not in txt2

  review.insert_feedback_for_item(item, "", scan_dir=str(content_dir))
  txt3 = md_file.read_text(encoding="utf-8")
  assert "+++" not in txt3.split("</summary>", 2)[2]
  assert f"{aranya_pp}\n" in txt3

  # State roundtrip outside git
  state = review.load_review_state(str(content_dir), cache_dir=cache_dir)
  state["decisions"][item.item_id] = "accept"
  review.save_review_state(str(content_dir), state, cache_dir=cache_dir)
  reloaded = review.load_review_state(str(content_dir), cache_dir=cache_dir)
  assert reloaded["decisions"][item.item_id] == "accept"


def test_split_static_nested_js_include_dedup_and_prefill_sync(tmp_path: Path):
  site = tmp_path / "vedAH_yajuH"
  static_vp = site / "static" / "ek" / "vishvAsa-prastutiH"
  static_tk = site / "static" / "ek" / "sarvASh_TIkAH"
  content_dir = site / "content" / "ek"
  cross_tk_dir = tmp_path / "vedAH" / "static" / "av" / "sarvASh_TIkAH"
  static_vp.mkdir(parents=True)
  static_tk.mkdir(parents=True)
  content_dir.mkdir(parents=True)
  cross_tk_dir.mkdir(parents=True)

  vp_file = static_vp / "01.md"
  tk_file = static_tk / "01.md"
  vp_file.write_text("अ᳓ग्नये **[[स्वाहा᳓|स्वा᳓हा]]**\n", encoding="utf-8")
  tk_file.write_text(
    "<details open><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अ᳓ग्नये (*TS*-5)\n"
    "- स्वाहा᳓ → **स्वा᳓हा** (*TS*-0/10, *RV*-0/8)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  # Historical pp_only pair (VP has NO [[OLD|NEW]]) must NOT be emitted
  (static_vp / "00_hist.md").write_text("स᳓रस्-वते᳓ ऽनु मन्यस्व।\n", encoding="utf-8")
  (static_tk / "00_hist.md").write_text(
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- स᳓रस्-व᳓ते → **स᳓रस्-वते** (*TS*-5)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  # Composite static VP file with <div class="js_include"> wrapping 01.md AND stale prefill to already-resolved 02_clean.md
  (static_vp / "02_clean.md").write_text("या᳓ **दे᳓वी**\n", encoding="utf-8")
  (static_tk / "02_clean.md").write_text(
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- याः᳓ (*RV*-5)\n- दे᳓वी (*RV*-5)\n\n</details>\n",
    encoding="utf-8",
  )
  comp_vp = static_vp / "99_comp.md"
  comp_vp.write_text(
    '<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/01.md" open>\n'
    "अ᳓ग्नये **[[स्वाहा᳓|स्वा᳓हा]]**\n"
    "</div>\n"
    '<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/02_clean.md" open>\n'
    "या᳓ [[दे᳓वी|देवी᳓]]\n"
    "</div>\n",
    encoding="utf-8",
  )

  # Cross-repo pairing (no sibling in static_tk) via host content file whose commentary contains ##### headings
  cross_vp = static_vp / "03_cross.md"
  cross_tk = cross_tk_dir / "26_cross.md"
  cross_vp.write_text("कृत्या᳓ [[व्यज्यते|व्य᳙ज्यते]] ।\n", encoding="utf-8")
  cross_tk.write_text(
    "<details><summary>Whitney</summary>\n\n##### Notes\nCross note\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- कृत्या᳓ (*RV*-2)\n"
    "- वि → **वि᳓** (*RV*-952)\n"
    "- अज्यते (*MS*-1)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  # Two host content files referencing includes (one prefilled, one unfilled) + cross-repo pairing
  host_prefilled = content_dir / "host_prefilled.md"
  host_unfilled = content_dir / "host_unfilled.md"
  host_prefilled.write_text(
    '<div class="js_include" url="/vedAH_yajuH/ek/prose.md">\n'
    '<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/01.md" open>\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "अ᳓ग्नये **[[स्वाहा᳓|स्वा᳓हा]]**\n\n"
    "</details>\n"
    "</div>\n"
    '<div class="js_include" url="/vedAH_yajuH/ek/sarvASh_TIkAH/01.md">\n'
    "<details open><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अ᳓ग्नये (*TS*-5)\n"
    "- स्वाहा᳓ → **स्वा᳓हा** (*TS*-0/10, *RV*-0/8)\n\n"
    "</details>\n"
    "</div>\n"
    "</div>\n"
    '<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/03_cross.md" open></div>\n'
    '<div class="js_include" url="/vedAH/av/sarvASh_TIkAH/26_cross.md">\n'
    "<details><summary>Whitney</summary>\n\n##### Notes\nCross note\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- कृत्या᳓ (*RV*-2)\n"
    "- वि → **वि᳓** (*RV*-952)\n"
    "- अज्यते (*MS*-1)\n\n"
    "</details>\n"
    "</div>\n",
    encoding="utf-8",
  )
  host_unfilled.write_text(
    '<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/01.md" open></div>\n'
    '<div class="js_include" url="/vedAH_yajuH/ek/sarvASh_TIkAH/01.md"></div>\n',
    encoding="utf-8",
  )

  # Scanning static root skips historical pp_only, ignores stale prefill in 99_comp.md, dedups 01.md, and pairs 03_cross.md!
  static_scan = review.scan_directory(str(site / "static" / "ek"))
  assert len(static_scan["items"]) == 2
  by_vp_name = {os.path.basename(x.vp_file or ""): x for x in static_scan["items"]}
  assert set(by_vp_name) == {"01.md", "03_cross.md"}
  it01 = by_vp_name["01.md"]
  it03 = by_vp_name["03_cross.md"]
  assert os.path.normpath(str(vp_file)) in it01.relevant_files
  assert os.path.normpath(str(tk_file)) in it01.relevant_files
  assert os.path.normpath(str(comp_vp)) in it01.host_files
  assert it03.kind == "both"
  assert it03.pp_file == os.path.normpath(str(cross_tk))
  assert "वि᳓" in it03.pp_line_core

  # Verify vishvAsa-relative paths everywhere including to_dict and file summaries
  d01 = it01.to_dict(hugo_base_dir=str(tmp_path))
  assert d01["rel_path"] == "vedAH_yajuH/static/ek/vishvAsa-prastutiH/01.md"
  assert d01["pp_rel"] == "vedAH_yajuH/static/ek/sarvASh_TIkAH/01.md"
  assert "vedAH_yajuH/static/ek/vishvAsa-prastutiH/99_comp.md" in d01["host_files_rel"]
  assert all(rf["short"].startswith(("vedAH_yajuH/", "vedAH/")) for rf in d01["relevant_files"])
  sums = review.compute_file_summaries(static_scan, {"decisions": {}, "file_overrides": {}})
  assert all(s["rel_display"].startswith(("vedAH_yajuH/", "vedAH/")) for s in sums)

  # Scanning content deduplicates host_prefilled and host_unfilled to canonical static files and pairs 03_cross
  content_scan = review.scan_directory(str(content_dir))
  assert len(content_scan["items"]) == 2
  by_vp_c = {os.path.basename(x.vp_file or ""): x for x in content_scan["items"]}
  it = by_vp_c["01.md"]
  assert it.pp_file == os.path.normpath(str(tk_file))
  assert it.vp_file == os.path.normpath(str(vp_file))
  assert os.path.normpath(str(host_prefilled)) in it.host_files
  assert os.path.normpath(str(host_unfilled)) in it.host_files
  assert by_vp_c["03_cross.md"].kind == "both"
  assert by_vp_c["03_cross.md"].pp_file == os.path.normpath(str(cross_tk))

  # Feedback inserted into canonical static pp_file syncs prefilled host without touching unfilled host
  res = review.insert_feedback_for_item(
    it,
    "Confirm svara here",
    sync_prefills=True,
    hugo_base_dir=str(tmp_path),
    scan_dir=str(content_dir),
  )
  assert os.path.normpath(str(tk_file)) in res["edited_files"]
  assert os.path.normpath(str(host_prefilled)) in res["refreshed_hosts"]
  assert "+++(Confirm svara here!!)+++" in tk_file.read_text(encoding="utf-8")
  assert "+++(Confirm svara here!!)+++" in host_prefilled.read_text(encoding="utf-8")
  assert "url=" in host_unfilled.read_text(encoding="utf-8") and "+++" not in host_unfilled.read_text(encoding="utf-8")


def test_sandhi_compound_fallback_alignment():
  pp_items = [
    reconciler.PadapathaItem(ar="अ᳓पः", ref="अपः᳓", prov="", vyat=True, solid=True),
    reconciler.PadapathaItem(ar="अशान", ref="अशान", prov="", vyat=False, solid=True),
    reconciler.PadapathaItem(ar="आचार्य-अधी᳓नः", ref="आचार्य-अधी᳓नः", prov="", vyat=False, solid=True),
    reconciler.PadapathaItem(ar="वि", ref="वि᳓", prov="", vyat=True, solid=True),
    reconciler.PadapathaItem(ar="अज्यते", ref="अज्यते", prov="", vyat=False, solid=True),
  ]
  assert review._fallback_match_pp_index("अ᳓पोऽशान", "अपो᳙ऽशान", pp_items) == 0
  assert review._fallback_match_pp_index("आचार्याधीनो᳓", "आचार्याधी᳓नो", pp_items) == 2
  assert review._fallback_match_pp_index("व्यज्यते", "व्य᳙ज्यते", pp_items) == 3


def test_vp_only_feedback_fallback_and_scoped_git_commit_via_fastapi(tmp_path: Path):
  repo = tmp_path / "vedAH_yajuH"
  _init_git_repo(repo)
  content_dir = repo / "content" / "kAThakam" / "saMhitA" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)

  accepted_file = content_dir / "01_accepted.md"
  vp_only_file = content_dir / "02_vp_only.md"
  unrelated_dirty = repo / "content" / "unrelated_dirty.md"
  unrelated_staged = repo / "content" / "unrelated_staged.md"
  untracked_new = content_dir / "03_untracked_new.md"

  accepted_file.write_text("# initial\n", encoding="utf-8")
  vp_only_file.write_text("# initial\n", encoding="utf-8")
  unrelated_dirty.write_text("clean\n", encoding="utf-8")
  unrelated_staged.write_text("clean\n", encoding="utf-8")
  _git(repo, "add", ".")
  _git(repo, "commit", "-m", "initial corpus")

  # Introduce dirty modifications and an unrelated pre-staged change simulating another active session
  unrelated_staged.write_text("concurrent staged edit\n", encoding="utf-8")
  _git(repo, "add", str(unrelated_staged.relative_to(repo)))
  unrelated_dirty.write_text("concurrent unstaged edit\n", encoding="utf-8")

  accepted_file.write_text(
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "अ᳓ग्निम् **[[ई᳓ळे|ईळे᳓]]**\n\n"
    "</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- ई᳓ळे → **ईळे᳓** (*RV*-0/5)\n\n"
    "</details>\n",
    encoding="utf-8",
  )
  vp_only_file.write_text(
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "स᳓मिधा **[[अ᳓ग्निम्|अग्नि᳓म्]]**\n\n"
    "</details>\n",
    encoding="utf-8",
  )
  untracked_new.write_text(
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "इ᳓डया **[[पदे᳓|प᳓दे]]**\n\n"
    "</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- पदे᳓ → **प᳓दे** (*RV*-0/3)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  app = review_gui.create_app(str(content_dir), default_n=2, cache_dir=str(tmp_path / "cache"))
  client = TestClient(app)

  assert client.get("/").status_code == 200
  presets = client.get("/api/presets").json()
  assert presets["default_n"] == 2

  items_resp = client.get("/api/items", params={"n_context": 2, "page_size": 50}).json()
  assert items_resp["filtered_total"] == 3
  items_by_rel = {os.path.basename(it["display_file"]): it for it in items_resp["items"]}
  assert set(items_by_rel) == {"01_accepted.md", "02_vp_only.md", "03_untracked_new.md"}
  assert items_by_rel["02_vp_only.md"]["kind"] == "vp_only"

  # Submit Accept on modified file and untracked new file -> edits only विश्वास-प्रस्तुतिः, leaves पद-पाठः intact
  sub1 = client.post(
    "/api/submit",
    json={"item_id": items_by_rel["01_accepted.md"]["item_id"], "decision": "accept"},
  ).json()
  sub2 = client.post(
    "/api/submit",
    json={"item_id": items_by_rel["03_untracked_new.md"]["item_id"], "decision": "accept"},
  ).json()
  assert sub1["decision"] == "accept"
  assert "अ᳓ग्निम् **ईळे᳓**" in accepted_file.read_text(encoding="utf-8")
  assert "- ई᳓ळे → **ईळे᳓** (*RV*-0/5)" in accepted_file.read_text(encoding="utf-8")
  assert "इ᳓डया **प᳓दे**" in untracked_new.read_text(encoding="utf-8")
  assert "- पदे᳓ → **प᳓दे** (*RV*-0/3)" in untracked_new.read_text(encoding="utf-8")

  marked = set(sub2["summary"]["marked_files"])
  assert str(accepted_file) in marked
  assert str(untracked_new) in marked
  assert str(vp_only_file) not in marked

  # Submit Reject + Feedback together on vp_only item -> keeps OLD in VP and appends +++(FEEDBACK!!)+++
  sub_vp = client.post(
    "/api/submit",
    json={
      "item_id": items_by_rel["02_vp_only.md"]["item_id"],
      "decision": "reject",
      "feedback_text": "Verify udātta shift",
    },
  ).json()
  assert sub_vp["decision"] == "reject"
  assert sub_vp["existing_feedback"] == "Verify udātta shift!!"
  vp_txt = vp_only_file.read_text(encoding="utf-8")
  assert "**अ᳓ग्निम्**" in vp_txt and "[[अ᳓ग्निम्|अग्नि᳓म्]]" not in vp_txt
  assert "+++(Verify udātta shift!!)+++" in vp_txt

  # Status filter counts match
  assert client.get("/api/items", params={"status_filter": "accept"}).json()["filtered_total"] == 2
  assert client.get("/api/items", params={"status_filter": "reject"}).json()["filtered_total"] == 1
  assert client.get("/api/items", params={"status_filter": "has_feedback"}).json()["filtered_total"] == 1
  assert client.get("/api/items", params={"status_filter": "pending"}).json()["filtered_total"] == 0

  # Diff endpoint works for modified file
  diff_resp = client.get("/api/diff", params={"file_path": str(accepted_file)}).json()
  assert "ईळे᳓" in diff_resp["diff"]

  # Commit ONLY the marked files via /api/commit and verify concurrent staged + dirty files survive intact!
  commit_resp = client.post(
    "/api/commit",
    json={"file_paths": sorted(marked), "commit_message": "Accept verified accent suggestions"},
  ).json()
  assert len(commit_resp["results"]) == 1
  res0 = commit_resp["results"][0]
  assert res0["sha"]
  assert res0["preserved_pre_staged"] == 1
  committed_names = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
  assert set(committed_names) == {
    str(accepted_file.relative_to(repo)),
    str(untracked_new.relative_to(repo)),
  }

  # Concurrent pre-staged file is STILL staged; concurrent dirty file is STILL unstaged-dirty; vp_only holds rejected+feedback
  assert _git(repo, "diff", "--cached", "--name-only").strip() == "content/unrelated_staged.md"
  status_lines = _git(repo, "status", "--porcelain").splitlines()
  assert "M  content/unrelated_staged.md" in status_lines
  assert " M content/unrelated_dirty.md" in status_lines
  assert any("02_vp_only.md" in ln for ln in status_lines)
  assert not any("01_accepted.md" in ln or "03_untracked_new.md" in ln for ln in status_lines)
  assert commit_resp["summary"]["marked_files"] == []


def test_submit_accept_reject_only_alters_prastuti_and_handles_siblings(tmp_path: Path):
  site = tmp_path / "vedAH_yajuH"
  static_vp = site / "static" / "ek" / "vishvAsa-prastutiH"
  static_tk = site / "static" / "ek" / "sarvASh_TIkAH"
  static_vp.mkdir(parents=True)
  static_tk.mkdir(parents=True)

  vp_file = static_vp / "05_dup.md"
  tk_file = static_tk / "05_dup.md"
  orig_tk = (
    "<details open><summary>पद-पाठः (यान्त्रिकः - 2/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- ते → **ते᳓** (*RV*-10)\n"
    "- ते → **ते᳓** (*RV*-10)\n\n"
    "</details>\n"
  )
  vp_file.write_text('+++\ntitle = "05"\n+++\n\n[[ते|ते᳓]] च [[ते|ते᳓]]\n', encoding="utf-8")
  tk_file.write_text(orig_tk, encoding="utf-8")

  app = review_gui.create_app(str(site / "static" / "ek"), default_n=2, cache_dir=str(tmp_path / "cache"))
  client = TestClient(app)
  items = client.get("/api/items").json()["items"]
  assert len(items) == 2

  # Accept item 0, Reject item 1
  r0 = client.post("/api/submit", json={"item_id": items[0]["item_id"], "decision": "accept"}).json()
  assert r0["vp_raw_body"] == "ते᳓ च [[ते|ते᳓]]"
  assert tk_file.read_text(encoding="utf-8") == orig_tk

  r1 = client.post("/api/submit", json={"item_id": items[1]["item_id"], "decision": "reject"}).json()
  assert r1["vp_raw_body"] == "ते᳓ च ते"
  assert tk_file.read_text(encoding="utf-8") == orig_tk

  # Flip item 0 Accept -> Reject, leaving item 1 untouched
  r0_flip = client.post("/api/submit", json={"item_id": items[0]["item_id"], "decision": "reject"}).json()
  assert r0_flip["vp_raw_body"] == "ते च ते"
  assert tk_file.read_text(encoding="utf-8") == orig_tk

  # Submit feedback ONLY on item 0 -> padapatha gets +++(Check enclitic!!)+++ while VP remains 'ते च ते'
  r0_fb = client.post(
    "/api/submit",
    json={"item_id": items[0]["item_id"], "decision": "reject", "feedback_text": "Check enclitic"},
  ).json()
  assert "+++(Check enclitic!!)+++" in tk_file.read_text(encoding="utf-8")
  assert "ते च ते" in vp_file.read_text(encoding="utf-8")
  assert r0_fb["existing_feedback"] == "Check enclitic!!"


def test_vp_decision_fallback_after_external_edit_and_vp_feedback_sibling_sync(tmp_path: Path):
  from fastapi.testclient import TestClient
  from doc_curation.sanskrit.accent import review_gui

  site = tmp_path / "vishvAsa" / "vedAH_yajuH"
  static_vp = site / "static" / "ek" / "vishvAsa-prastutiH"
  static_tk = site / "static" / "ek" / "sarvASh_TIkAH"
  static_vp.mkdir(parents=True)
  static_tk.mkdir(parents=True)

  vp_file = static_vp / "10_yad.md"
  tk_file = static_tk / "10_yad.md"
  vp_file.write_text(
    '+++\ntitle = "10"\n+++\n\n[[सेन्द्रस्य|से᳓न्द्रस्य]] +++(note)+++ [[सगन्धर्वस्य|स᳓गन्धर्वस्य]]\n',
    encoding="utf-8",
  )
  tk_file.write_text(
    "<details open><summary>पद-पाठः (यान्त्रिकः - 2/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- सेन्द्रस्य → **से᳓न्द्रस्य** (बहुव्रीहिः पा॰ ६.२.१)\n"
    "- सगन्धर्वस्य → **स᳓गन्धर्वस्य** (बहुव्रीहिः पा॰ ६.२.१)\n\n"
    "</details>\n",
    encoding="utf-8",
  )

  app = review_gui.create_app(str(site / "static" / "ek"), default_n=2, cache_dir=str(tmp_path / "cache"))
  client = TestClient(app)
  items = client.get("/api/items").json()["items"]
  assert len(items) == 2

  # 1. Writing VP feedback on item 0 must keep sibling item 1's vp_raw_body & highlight synced
  fb_resp = client.post(
    "/api/feedback",
    json={"item_id": items[0]["item_id"], "feedback_text": "VP note", "target_mode": "vp"},
  )
  assert fb_resp.status_code == 200
  pending_after_fb = client.get("/api/items", params={"status_filter": "pending"}).json()
  assert pending_after_fb["summary"]["counts"]["pending"] == 1
  assert pending_after_fb["summary"]["counts"]["with_feedback"] == 1
  assert [x["item_id"] for x in pending_after_fb["items"]] == [items[1]["item_id"]]
  fb_only = client.get("/api/items", params={"status_filter": "has_feedback"}).json()
  assert [x["item_id"] for x in fb_only["items"]] == [items[0]["item_id"]]
  assert any(f["counts"]["pending"] == 1 and f["counts"]["with_feedback"] == 1 for f in fb_only["summary"]["files"])
  r1_ok = client.post("/api/submit", json={"item_id": items[1]["item_id"], "decision": "accept"})
  assert r1_ok.status_code == 200
  assert "स᳓गन्धर्वस्य" in vp_file.read_text(encoding="utf-8")
  assert "[[सगन्धर्वस्य|स᳓गन्धर्वस्य]]" not in vp_file.read_text(encoding="utf-8")

  # 2. Unrelated external edit on disk (without rescanning) still allows token-level fallback on remaining item 0
  disk = vp_file.read_text(encoding="utf-8").replace("+++(note)+++", "+++(edited elsewhere)+++")
  vp_file.write_text(disk, encoding="utf-8")
  r0_ok = client.post("/api/submit", json={"item_id": items[0]["item_id"], "decision": "accept"})
  assert r0_ok.status_code == 200
  assert "से᳓न्द्रस्य" in vp_file.read_text(encoding="utf-8")

  # 3. If the target token itself is resolved externally before rescanning, return an actionable Ctrl+R error
  vp_file.write_text(
    vp_file.read_text(encoding="utf-8").replace("से᳓न्द्रस्य", "EXTERNALLY_CHANGED"),
    encoding="utf-8",
  )
  r0_err = client.post("/api/submit", json={"item_id": items[0]["item_id"], "decision": "reject"})
  assert r0_err.status_code == 400
  assert "Ctrl+R" in r0_err.json()["detail"]


def test_review_gui_embedded_js_syntax(tmp_path: Path):
  import json
  import shutil

  m = re.search(r"<script>(.*?)</script>", review_gui._RENDERED_HTML, re.S)
  assert m is not None
  js = m.group(1)
  assert "--dev-font-size: 26px;" in review_gui._RENDERED_HTML
  assert "applyEditorFont" in review_gui._RENDERED_HTML
  assert 'id="refreshBtn"' in review_gui._RENDERED_HTML and 'onclick="reloadUi()"' in review_gui._RENDERED_HTML
  assert 'id="undoBtn"' in review_gui._RENDERED_HTML and 'onclick="undoLastAction()"' in review_gui._RENDERED_HTML
  assert "Included in:" not in review_gui._RENDERED_HTML
  assert 'document.getElementById("dirInput")' in js
  assert "renderFullVP" in js
  assert "formatPadapathaLineHtml" in js
  assert 'ev.key === "1"' in js and 'ev.key === "2"' in js and 'ev.key === "3"' in js
  assert 'ev.key === "Enter"' in js
  if shutil.which("node"):
    js_path = tmp_path / "review_gui.js"
    js_path.write_text(js, encoding="utf-8")
    subprocess.check_call(["node", "--check", str(js_path)])

    vp_body_sample = "+++(टीका)+++ गृ᳓ह्याभ्यस् [[अवसा᳓नेभ्य᳓स्|अवसा᳓नेभ्यस्]] **[[स्वाहा᳓|स्वा᳓हा]]**"
    tok = "[[स्वाहा᳓|स्वा᳓हा]]"
    tok_s = vp_body_sample.index(tok)
    sample_data = {
      "filtered_total": 1,
      "page": 1,
      "page_size": 25,
      "total_pages": 1,
      "summary": {
        "total_items": 1,
        "counts": {"pending": 1, "accept": 0, "reject": 0, "with_feedback": 0},
        "files": [],
        "marked_files": [],
      },
      "items": [
        {
          "item_id": "abc123",
          "rel_path": "vedAH_yajuH/static/ek/vishvAsa-prastutiH/01.md",
          "section_heading": "",
          "kind": "both",
          "vp_summary": "विश्वास-प्रस्तुतिः",
          "vp_raw_body": vp_body_sample,
          "vp_highlight_ranges": [[tok_s, tok_s + len(tok)]],
          "pp_summary": "पद-पाठः (यान्त्रिकः)",
          "pp_file": "/tmp/tk.md",
          "pp_target_idx": 1,
          "pp_total_lines": 3,
          "pp_context_before": ["- गृ᳓ह्याभ्यः (*TS*-1)"],
          "pp_target_line": "- स्वाहा᳓ → **स्वा᳓हा** (*TS*-0/10) +++(Are you sure?!!)+++",
          "pp_context_after": ["- नमः᳓ (*RV*-5)"],
          "pp_goldendict": {"word": "स्वाहा", "pratipadika": "स्वाहा", "primary": "स्वाहा", "alternatives": []},
          "relevant_files": [
            {
              "path": "/tmp/vp.md",
              "vishvasa_rel": "vedAH_yajuH/static/ek/vishvAsa-prastutiH/01.md",
              "role": "विश्वास-प्रस्तुतिः",
              "git_status": "clean",
            }
          ],
          "host_files_rel": ["vedAH_yajuH/content/ek/1.md"],
          "mula_preview": "",
          "existing_feedback": "Are you sure?!!",
          "decision": "pending",
        }
      ],
    }
    harness = (
      "const elems = {};\n"
      "const listeners = {};\n"
      "function makeEl(id) {\n"
      '  const val = id === "nInput" ? "3" : (id === "statusFilter" ? "pending" : (id.endsWith("Filter") ? "all" : ""));\n'
      "  const classes = new Set();\n"
      "  return {\n"
      "    id, value: val, textContent: '', innerHTML: '', checked: true, focused: false, style: {},\n"
      "    classList: {\n"
      "      toggle(c, f) { if (f === undefined ? !classes.has(c) : !!f) classes.add(c); else classes.delete(c); },\n"
      "      add(...cs) { cs.forEach(c => classes.add(c)); },\n"
      "      remove(...cs) { cs.forEach(c => classes.delete(c)); },\n"
      "      contains(c) { return classes.has(c); },\n"
      "    },\n"
      "    querySelectorAll(){ return []; }, scrollIntoView(){}, focus(){ this.focused = true; }, blur(){},\n"
      "  };\n"
      "}\n"
      "global.document = {\n"
      "  activeElement: null,\n"
      "  documentElement: { style: { setProperty(){} } },\n"
      "  getElementById(id) { if (!elems[id]) elems[id] = makeEl(id); return elems[id]; },\n"
      "  querySelectorAll() { return []; },\n"
      "  addEventListener(evt, fn) { listeners[evt] = fn; },\n"
      "};\n"
      "let reloadedCount = 0;\n"
      "global.window = { location: { reload() { reloadedCount += 1; } } };\n"
      "global.localStorage = { getItem(){ return null; }, setItem(){} };\n"
      "const fetchedCalls = [];\n"
      "global.fetch = async (url, opts) => { fetchedCalls.push({ url, body: opts && opts.body }); return { ok: true, json: async () => ({ dir_path: '/tmp/ek', presets: [], default_n: 3, current_dir: '/tmp/ek', items: [], page: 1, total_pages: 1, filtered_total: 0, page_size: 25, item: null, summary: { total_items: 1, counts: { pending: 0, accept: 1, reject: 0, with_feedback: 0 }, files: [], marked_files: [] } }) }; };\n"
      + js.replace("init();", "")
      + f"\nconst data = {json.dumps(sample_data)};\n"
      + "latestSummary = data.summary;\n"
      + "currentItems = data.items;\n"
      + "focusedIdx = 0;\n"
      + "draftDecisions = { abc123: 'pending' };\n"
      + "renderSummary(data.summary);\n"
      + "renderCards(data);\n"
      + 'const out = elems["cardsContainer"].innerHTML;\n'
      + 'if (!out.includes("id=\\"card_0\\"") || !out.includes(\'<span class="inline-note">(टीका)</span>\') || out.includes("+++(टीका)+++") || !out.includes("sug-other") || !out.includes("inline-feedback-tag") || !out.includes("Reject") || !out.includes("Submit") || out.includes("Included in:")) {\n'
      + '  throw new Error("Unexpected rendered card markup: " + out);\n'
      + "}\n"
      + "function makeRadioLabel(val) {\n"
      + "  const lbl = makeEl('');\n"
      + "  const inp = { value: val, checked: false };\n"
      + "  lbl.querySelector = () => inp;\n"
      + "  lbl._inp = inp;\n"
      + "  return lbl;\n"
      + "}\n"
      + "const rgLblAccept = makeRadioLabel('accept');\n"
      + "const rgLblReject = makeRadioLabel('reject');\n"
      + 'elems["radioGroup_0"] = { querySelectorAll() { return [rgLblAccept, rgLblReject]; } };\n'
      + 'listeners["keydown"]({ key: "2", code: "Digit2", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + 'if (draftDecisions["abc123"] !== "reject" || !rgLblReject._inp.checked || !rgLblReject.classList.contains("sel-reject")) throw new Error("Alt+2 did not select reject");\n'
      + 'listeners["keydown"]({ key: "2", code: "Digit2", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + 'if (draftDecisions["abc123"] !== "pending" || rgLblAccept._inp.checked || rgLblReject._inp.checked || rgLblReject.classList.contains("sel-reject")) throw new Error("Second Alt+2 did not clear reject radio");\n'
      + 'listeners["keydown"]({ key: "2", code: "Digit2", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + 'if (draftDecisions["abc123"] !== "reject" || !rgLblReject._inp.checked) throw new Error("Third Alt+2 did not re-select reject");\n'
      + '(async () => {\n'
      + '  if (document.getElementById("statusFilter").value !== "pending") {\n'
      + '    throw new Error("Expected statusFilter to default to pending");\n'
      + '  }\n'
      + '  document.getElementById("statusFilter").value = "all";\n'
      + '  // Browser DOM initializes fbInput value from item existing_feedback\n'
      + '  elems["fbInput_abc123"] = makeEl("fbInput_abc123");\n'
      + '  elems["fbInput_abc123"].value = "Are you sure?!!";\n'
      + '  // Ctrl+Enter forces Accept + Submit even when radio was Reject\n'
      + '  listeners["keydown"]({ key: "Enter", altKey: false, ctrlKey: true, metaKey: false, shiftKey: false, target: { id: "fbInput_abc123", tagName: "INPUT" }, preventDefault(){} });\n'
      + '  await new Promise(r => setTimeout(r, 20));\n'
      + '  if (!fetchedCalls.length || fetchedCalls[0].url !== "/api/submit" || !fetchedCalls[0].body.includes(\'"decision":"accept"\')) {\n'
      + '    throw new Error("Ctrl+Enter did not Accept+Submit: " + JSON.stringify(fetchedCalls));\n'
      + '  }\n'
      + '  if (!collapsedCards["abc123"] || !elems["card_0"].outerHTML.includes(" collapsed")) {\n'
      + '    throw new Error("Card did not collapse after submit");\n'
      + '  }\n'
      + '  toggleCardCollapse(0, false);\n'
      + '  if (collapsedCards["abc123"] || elems["card_0"].outerHTML.includes(" collapsed")) {\n'
      + '    throw new Error("Card did not expand on toggleCardCollapse");\n'
      + '  }\n'
      + '  listeners["keydown"]({ key: "ArrowLeft", ctrlKey: false, altKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
      + '  if (!collapsedCards["abc123"] || !elems["card_0"].outerHTML.includes(" collapsed")) {\n'
      + '    throw new Error("ArrowLeft did not collapse focused card");\n'
      + '  }\n'
      + '  listeners["keydown"]({ key: "ArrowRight", ctrlKey: false, altKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
      + '  if (collapsedCards["abc123"] || elems["card_0"].outerHTML.includes(" collapsed")) {\n'
      + '    throw new Error("ArrowRight did not expand focused card");\n'
      + '  }\n'
      + '  listeners["keydown"]({ key: "1", code: "Digit1", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + '  if (draftDecisions["abc123"] !== "pending" || rgLblAccept._inp.checked || rgLblReject._inp.checked) throw new Error("Alt+1 while accept selected did not clear radio");\n'
      + '  listeners["keydown"]({ key: "1", code: "Digit1", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + '  if (draftDecisions["abc123"] !== "accept" || !rgLblAccept._inp.checked || !rgLblAccept.classList.contains("sel-accept")) throw new Error("Second Alt+1 did not select accept");\n'
      + '  listeners["keydown"]({ key: "3", code: "Digit3", altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: {}, preventDefault(){} });\n'
      + '  if (!elems["fbInput_abc123"].focused) throw new Error("Alt+3 did not focus feedback input");\n'
      + '  listeners["keydown"]({ key: "Enter", altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, target: { id: "fbInput_abc123", tagName: "INPUT" }, preventDefault(){} });\n'
  + '  await new Promise(r => setTimeout(r, 20));\n'
      + '  if (fetchedCalls.length < 2 || fetchedCalls[1].url !== "/api/submit") {\n'
      + '    throw new Error("Enter did not submit: " + JSON.stringify(fetchedCalls));\n'
      + '  }\n'
  + '  if (!out.includes("openItemFileInIdea(0)") || !out.includes("openRelevantFileInIdea(0, 0)") || !out.includes(\'class="file-link"\') || !out.includes("openItemGoldenDict(0, 0)") || !out.includes(\'id="ppTarget_abc123">\')) {\n'
  + '    throw new Error("Missing IntelliJ or GoldenDict inline links in target line: " + out);\n'
  + '  }\n'
  + '  const targetLineHtml = out.slice(out.indexOf(\'id="ppTarget_abc123">\'), out.indexOf(\'</div>\', out.indexOf(\'id="ppTarget_abc123">\')));\n'
  + '  if (!targetLineHtml.includes("openItemGoldenDict(0, 0)") || !targetLineHtml.includes(\'class="gd-inline"\')) {\n'
  + '    throw new Error("GoldenDict link not placed inside ppTarget line: " + targetLineHtml);\n'
  + '  }\n'
  + '  // Reload button reloads UI via window.location.reload()\n'
  + '  reloadUi();\n'
  + '  if (reloadedCount !== 1) throw new Error("reloadUi did not call window.location.reload()");\n'
  + '  // Ctrl+Z inside a text input must NOT hijack native text undo\n'
  + '  const lenBeforeTextUndo = fetchedCalls.length;\n'
  + '  listeners["keydown"]({ key: "z", ctrlKey: true, altKey: false, metaKey: false, shiftKey: false, target: { id: "fbInput_abc123", tagName: "INPUT", type: "text" }, preventDefault(){} });\n'
  + '  await new Promise(r => setTimeout(r, 20));\n'
  + '  if (fetchedCalls.length !== lenBeforeTextUndo) throw new Error("Ctrl+Z inside text input should not invoke card undo");\n'
  + '  // Ctrl+Z outside text input undoes the submitted accept -> restores pending\n'
  + '  listeners["keydown"]({ key: "z", ctrlKey: true, altKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
  + '  await new Promise(r => setTimeout(r, 20));\n'
  + '  const undoCall = fetchedCalls.find((c, ci) => ci >= lenBeforeTextUndo && c.url === "/api/submit");\n'
  + '  if (!undoCall || !undoCall.body.includes(\'"decision":"pending"\')) {\n'
  + '    throw new Error("Ctrl+Z did not restore previous pending decision: " + JSON.stringify(fetchedCalls));\n'
  + '  }\n'
  + '  // Ctrl+R rescans directory preserving view even when currentItems is empty\n'
  + '  document.getElementById("dirInput").value = "/tmp/ek";\n'
  + '  selectedFile = "/tmp/ek/1.md";\n'
  + '  currentPage = 3;\n'
  + '  const lenBeforeScan = fetchedCalls.length;\n'
  + '  listeners["keydown"]({ key: "r", ctrlKey: true, altKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
  + '  await new Promise(r => setTimeout(r, 20));\n'
  + '  const scanCall = fetchedCalls.find((c, ci) => ci >= lenBeforeScan && c.url === "/api/scan");\n'
  + '  if (!scanCall || selectedFile !== "/tmp/ek/1.md") {\n'
  + '    throw new Error("Ctrl+R did not rescan while preserving view: " + JSON.stringify(fetchedCalls));\n'
  + '  }\n'
  + '  // Status filter pills & Alt+P/A/R/W/L/0 shortcuts update statusFilter, query /api/items, and mark active pill\n'
  + '  for (const [st, activeId] of [["pending", "statPending"], ["accept", "statAccept"], ["reject", "statReject"], ["has_feedback", "statHold"], ["all", "statTotal"]]) {\n'
  + '    const before = fetchedCalls.length;\n'
  + '    await setStatusFilter(st);\n'
  + '    if (document.getElementById("statusFilter").value !== st) throw new Error("statusFilter mismatch for " + st);\n'
  + '    if (!document.getElementById(activeId).classList.contains("active")) throw new Error(activeId + " not active for " + st);\n'
  + '    const call = fetchedCalls.slice(before).find(c => c.url.startsWith("/api/items?"));\n'
  + '    if (!call || !call.url.includes("status_filter=" + st)) throw new Error("Missing status_filter in /api/items: " + JSON.stringify(call));\n'
  + '  }\n'
  + '  // Active card pair highlighting renders on card_0 and tracks j/k navigation\n'
  + '  const card0 = makeEl("card_0"); card0.classList.add("focused");\n'
  + '  const card1 = makeEl("card_1");\n'
  + '  document.querySelectorAll = (sel) => sel === "#cardsContainer > .card" ? [card0, card1] : [];\n'
  + '  currentItems = [data.items[0], Object.assign({}, data.items[0], { item_id: "def456" })];\n'
  + '  focusedIdx = 0;\n'
  + '  renderCards({ filtered_total: 2, page_size: 25 });\n'
  + '  const multiOut = elems["cardsContainer"].innerHTML;\n'
  + '  if (!multiOut.includes("active-badge") || !multiOut.includes(\'onfocusin="setFocused(0)"\') || !multiOut.includes(\'class="card dec-\' + (data.items[0].decision || "pending") + \' focused \')) {\n'
  + '    throw new Error("Active card pair missing focused highlight or badge: " + multiOut);\n'
  + '  }\n'
  + '  if (multiOut.split(\'id="card_1"\')[0].slice(-40).includes(" focused ")) {\n'
  + '    throw new Error("Inactive card_1 unexpectedly marked focused");\n'
  + '  }\n'
  + '  listeners["keydown"]({ key: "j", code: "KeyJ", altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
  + '  if (focusedIdx !== 1 || card0.classList.contains("focused") || !card1.classList.contains("focused")) {\n'
  + '    throw new Error("j did not move focused highlight to card_1");\n'
  + '  }\n'
  + '  // Collapsed cards show the correction in the bigger editor font (var(--dev-font-size))\n'
  + '  const vpItem = Object.assign({}, data.items[0], { item_id: "vpCol", vp_sug_old: "स्वाहा᳓", vp_sug_new: "स्वा᳓हा" });\n'
  + '  const ppItem = Object.assign({}, data.items[0], { item_id: "ppCol", vp_sug_old: "", vp_sug_new: "", pp_line_core: "- अ᳓पः → **अपः᳓** (*TS*-1)" });\n'
  + '  collapsedCards["vpCol"] = true; collapsedCards["ppCol"] = true;\n'
  + '  currentItems = [vpItem, ppItem];\n'
  + '  renderCards({ filtered_total: 2, page_size: 25 });\n'
  + '  const colOut = elems["cardsContainer"].innerHTML;\n'
  + '  if (!colOut.includes(\'class="collapse-correction"\') || !colOut.includes("स्वाहा᳓") || !colOut.includes("स्वा᳓हा") || !colOut.includes("अ᳓पः") || !colOut.includes("अपः᳓")) {\n'
  + '    throw new Error("Collapsed summary missing large-font correction preview: " + colOut);\n'
  + '  }\n'
  + '  // Alt+P / Alt+A / Alt+R / Alt+W / Alt+L work even when currentItems is empty\n'
  + '  currentItems = [];\n'
  + '  for (const [key, code, expected] of [["p", "KeyP", "pending"], ["a", "KeyA", "accept"], ["r", "KeyR", "reject"], ["w", "KeyW", "has_feedback"], ["l", "KeyL", "all"], ["0", "Digit0", "all"], ["p", "KeyP", "pending"]]) {\n'
  + '    const before = fetchedCalls.length;\n'
  + '    listeners["keydown"]({ key, code, altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, target: { tagName: "BODY" }, preventDefault(){} });\n'
  + '    await new Promise(r => setTimeout(r, 10));\n'
  + '    if (document.getElementById("statusFilter").value !== expected) throw new Error("Alt+" + key + " did not set filter " + expected);\n'
  + '    const call = fetchedCalls.slice(before).find(c => c.url.startsWith("/api/items?"));\n'
  + '    if (!call || !call.url.includes("status_filter=" + expected)) throw new Error("Alt+" + key + " missing /api/items call");\n'
  + '  }\n'
      + '})();\n'
    )
    n_idx = review_gui._RENDERED_HTML.index('id="nInput"')
    ref_idx = review_gui._RENDERED_HTML.index('id="refreshBtn"')
    font_idx = review_gui._RENDERED_HTML.index('id="fontPxInput"')
    assert n_idx < ref_idx < font_idx
    assert '<option value="pending" selected>' in review_gui._RENDERED_HTML
    assert 'id="statPending"' in review_gui._RENDERED_HTML and "setStatusFilter('pending')" in review_gui._RENDERED_HTML
    assert ".card.focused {" in review_gui._RENDERED_HTML
    assert ".card.focused .active-badge { display: inline-flex; }" in review_gui._RENDERED_HTML
    assert ".collapse-correction {" in review_gui._RENDERED_HTML
    assert "font-size: var(--dev-font-size);" in review_gui._RENDERED_HTML.split(".collapse-correction {")[1].split("}")[0]
    assert "background: var(--accent-soft);" in review_gui._RENDERED_HTML
    run_js = tmp_path / "run_render.js"
    run_js.write_text(harness, encoding="utf-8")
    subprocess.check_call(["node", str(run_js)])


def test_open_in_intellij_endpoint_and_line_resolution(tmp_path: Path, monkeypatch):
  from fastapi.testclient import TestClient
  from doc_curation.sanskrit.accent import review_gui

  target = tmp_path / "09_mA_te.md"
  target.write_text(
    '+++\ntitle = "०९ मा ते"\n+++\n**मा᳓** ते गृहे᳓\nअन्य᳓त्र **[[व᳓धिष्ठा|वधिष्ठा]]**\n',
    encoding="utf-8",
  )

  launched: list[list[str]] = []
  monkeypatch.setattr(review_gui, "_resolve_idea_binary", lambda: "/usr/local/bin/idea-mock")
  monkeypatch.setattr(review_gui.subprocess, "Popen", lambda cmd, **kw: launched.append(list(cmd)))

  client = TestClient(review_gui.create_app(cache_dir=str(tmp_path / "cache")))

  r1 = client.post("/api/open_in_idea", json={"file_path": str(target), "needle": "[[व᳓धिष्ठा|वधिष्ठा]]"})
  assert r1.status_code == 200
  d1 = r1.json()
  assert d1["ok"] is True and d1["line"] == 5
  assert launched[-1] == ["/usr/local/bin/idea-mock", "--line", "5", str(target.resolve())]

  r2 = client.post("/api/open_in_idea", json={"file_path": str(target), "line": 4})
  assert r2.status_code == 200
  assert r2.json()["line"] == 4
  assert launched[-1] == ["/usr/local/bin/idea-mock", "--line", "4", str(target.resolve())]

  r_missing = client.post("/api/open_in_idea", json={"file_path": str(tmp_path / "nope.md")})
  assert r_missing.status_code == 404


def test_open_in_goldendict_and_pratipadika_lookup(tmp_path: Path, monkeypatch):
  from fastapi.testclient import TestClient
  from doc_curation.sanskrit.accent import review, review_gui

  gd_sup = review.resolve_goldendict_lookup("- सुपेश᳓सा (*TS*-0/1)")
  assert gd_sup["pratipadika"] == "सुपेशस्"
  assert gd_sup["primary"] == "सुपेशस्"
  assert "सुपेशसा" in gd_sup["alternatives"]

  gd_jiv = review.resolve_goldendict_lookup("- जी᳓वताम् (शतृ)")
  assert gd_jiv["pratipadika"] == "जीवत्"
  assert "जीवताम्" in gd_jiv["alternatives"]

  gd_dirgha = review.resolve_goldendict_lookup("- दीर्घायुः᳓ → **दीर्घ᳓-आयुः** (*RV*-2)")
  assert gd_dirgha["pratipadika"] in ("दीर्घायु", "दीर्घायुस्")

  launched: list[list[str]] = []
  monkeypatch.setattr(review_gui, "_resolve_goldendict_binary", lambda: "/usr/bin/goldendict-mock")
  monkeypatch.setattr(review_gui.subprocess, "Popen", lambda cmd, **kw: launched.append(list(cmd)))

  client = TestClient(review_gui.create_app(cache_dir=str(tmp_path / "cache")))
  resp = client.post("/api/open_in_goldendict", json={"word": "जी᳓वत्"})
  assert resp.status_code == 200
  data = resp.json()
  assert data["ok"] is True and data["word"] == "जीवत्"
  assert launched[-1] == ["/usr/bin/goldendict-mock", "जीवत्"]

  bad = client.post("/api/open_in_goldendict", json={"word": "   "})
  assert bad.status_code == 400


