from doc_curation.sanskrit.accent import (
  convert_tree_to_us_accents,
  dependent_to_us_preserving,
  split_frontmatter_verbatim,
  to_us_accents_markdown,
)


def test_split_frontmatter_verbatim_toml_and_yaml():
  toml_doc = '+++\ntitle = "अग्निमीळे"\nunicode_script = "devanagari"\n\n+++\nअ॒ग्निमी॑ळे।\n'
  fm, body = split_frontmatter_verbatim(toml_doc)
  assert fm == '+++\ntitle = "अग्निमीळे"\nunicode_script = "devanagari"\n\n+++\n'
  assert body == "अ॒ग्निमी॑ळे।\n"

  yaml_doc = "---\ntitle: या राका\n---\n\nया राका।\n"
  fm_y, body_y = split_frontmatter_verbatim(yaml_doc)
  assert fm_y == "---\ntitle: या राका\n---\n"
  assert body_y == "\nया राका।\n"

  assert split_frontmatter_verbatim("अ॒ग्निः\n") == ("", "अ॒ग्निः\n")


def test_to_us_accents_markdown_preserves_frontmatter_js_includes_and_tags():
  src = (
    '+++\n'
    'title = "०१ ध्रुव"\n\n'
    '+++\n'
    '## शीर्षकम्\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n'
    'अ॒ग्निमी॑ळे  \n'
    '</details>\n\n'
    '<div class="js_include" unfilled url="/repo/nested.md">\n'
    '<div class="inner">अ॒ग्निमी॑ळे</div>\n'
    '</div>\n\n'
    'अन्ते `अ॒ग्निः` इति।\n'
  )
  out = to_us_accents_markdown(src)
  # Frontmatter, headings without classical accents, summaries, js_include (even nested divs), and inline code stay verbatim.
  assert out.startswith('+++\ntitle = "०१ ध्रुव"\n\n+++\n## शीर्षकम्\n\n')
  assert '<details open><summary>विश्वास-प्रस्तुतिः</summary>\nअग्नि᳓मीळे  \n</details>' in out
  assert '<div class="js_include" unfilled url="/repo/nested.md">\n<div class="inner">अ॒ग्निमी॑ळे</div>\n</div>' in out
  assert 'अन्ते `अ॒ग्निः` इति।' in out

  # Running again is idempotent and leaves already-US text untouched byte-for-byte.
  assert to_us_accents_markdown(out) == out


def test_to_us_accents_markdown_atharva_and_wrapped_padas():
  av_doc = (
    '+++\ntitle = "०१ शं नो देवीरभिष्टये"\n+++\n'
    'शं नो॑ दे॒वीर॒भिष्ट॑य॒ आपो॑ भवन्तु पी॒तये॑ ।\n'
    'य॒ज्ञं या᳡मा॑हु॒र्भुव॑नस्य ।\n'
    'अ॒भि प्रेहि॑१॒ वाजि॑नि ओ३म् ।\n'
  )
  out = to_us_accents_markdown(av_doc)
  assert "शं᳓ नो देवी᳓रभि᳓ष्टय आ᳓पो भवन्तु पीत᳓ये ।" in out
  assert "यज्ञं᳓ या᳙माहुर्भु᳓वनस्य ।" in out
  assert "अभि᳓ प्रे᳓हि᳙ वा᳓जिनि ओ३म् ।\n" in out

  wrapped = (
    '+++\ntitle = "पादाः"\n+++\n'
    'इषे त्वा\n'
    'ऊर्जे त्वा॑ ।\n\n'
    'अत्र अन्या टिप्पनी।\n'
  )
  out_wrapped = to_us_accents_markdown(wrapped, pauses=r"[।॥,;]+")
  assert "इ᳓षे᳓ त्वा᳓\nऊ᳓र्जे᳓ त्वा ।" in out_wrapped
  assert "\nअत्र अन्या टिप्पनी।\n" in out_wrapped


def test_dependent_to_us_preserving_handles_av_svarita():
  mixed = "या᳓ या᳡मा॑हुः"
  converted = dependent_to_us_preserving(mixed)
  assert converted == "या᳓ या᳙माहुः"
  assert dependent_to_us_preserving("या᳡मा॑हुः") == "या᳙माहुः"


def test_convert_tree_to_us_accents_and_transitive_host_refresh(tmp_path):
  hugo_root = tmp_path / "hugo"
  repo_root = hugo_root / "repoA"
  static_dir = repo_root / "static" / "saMhitA"
  content_dir = repo_root / "content" / "sarva"
  static_dir.mkdir(parents=True)
  content_dir.mkdir(parents=True)

  src_file = static_dir / "01_agni.md"
  src_file.write_text(
    '+++\ntitle = "०१ अग्नि"\n\n+++\nअ॒ग्निमी॑ळे ॥\n',
    encoding="utf-8",
  )
  clean_file = static_dir / "02_clean.md"
  clean_file.write_text(
    '+++\ntitle = "०२ स्वच्छ"\n+++\nनमः ॥\n',
    encoding="utf-8",
  )

  host_file = content_dir / "01.md"
  host_file.write_text(
    '+++\ntitle = "होस्ट्"\n+++\n'
    '<div class="js_include" unfilled url="/repoA/saMhitA/01_agni.md">\n'
    '<details open><summary><h2>०१ अग्नि ...{Loading}...</h2></summary>\n'
    'अ॒ग्निमी॑ळे ॥\n'
    '</details>\n'
    '</div>\n',
    encoding="utf-8",
  )

  dry_report = convert_tree_to_us_accents(
    static_dir,
    refresh_host_dirs=[content_dir],
    hugo_base_dir=str(hugo_root),
    dry_run=True,
  )
  assert dry_report["changed_files"] == [str(src_file)]
  assert dry_report["updated_hosts"] == []
  assert "अ॒ग्निमी॑ळे" in src_file.read_text(encoding="utf-8")
  assert "अ॒ग्निमी॑ळे" in host_file.read_text(encoding="utf-8")

  report = convert_tree_to_us_accents(
    static_dir,
    refresh_host_dirs=[content_dir],
    hugo_base_dir=str(hugo_root),
    dry_run=False,
  )
  assert report["changed_files"] == [str(src_file)]
  assert report["updated_hosts"] == [str(host_file)]
  assert "अग्नि᳓मीळे ॥" in src_file.read_text(encoding="utf-8")
  host_updated = host_file.read_text(encoding="utf-8")
  assert "अग्नि᳓मीळे ॥" in host_updated
  assert "अ॒ग्निमी॑ळे" not in host_updated


def test_repair_gretil_svarita_leaks_and_preserves_genuine(tmp_path):
  from doc_curation.sanskrit.accent import (
    repair_gretil_svarita_leaks_in_vp,
    repair_tree_svarita_leaks,
  )

  # Spurious line-initial ᳙ on third pāda + single-accent spurious ᳙ resolved via PP,
  # while genuine kampa/kṣaipra/abhinihita/jātya svaritas are preserved verbatim.
  vp = (
    "अम्ब᳓यो यन्त्य᳓ध्वभिर्जाम᳓यो अध्वरीयता᳓म्।\n"
    "पृ᳙ञ्चती᳓र्म᳓धुना प᳓यः ॥\n"
    "व्य᳙हं᳓ स᳓र्वेण । कन्या᳙नां तन्वं᳙ सो᳙ ऽयं ।\n"
    "ध्रु᳙वायां ।\nशं᳙ ते ।\nकृ᳙णोमि ।\nजा᳙नीहि ॥\n"
    "ते᳓षा᳓ं च᳙ ते ।\nनै᳙नम् ॥"
  )
  pp = (
    "अ॒म्बयः॑। य॒न्ति॒। अ॒ध्वऽभिः॑। जा॒मयः॑। अ॒ध्व॒री॒य॒ताम्। पृ॒ञ्च॒तीः। मधु॑ना। पयः॑। "
    "वि। अ॒हम्। सर्वे॑ण। क॒न्या॑नाम्। त॒न्वम्। सः। अ॒यम्। "
    "ध्रु॒वाया॑म्। शम्। ते॒। कृ॒णोमि॑। जा॒नी॒हि॒। तेषा॑म्। च॒। ते॒। न। ए॒न॒म्।"
  )
  fixed, n_fx = repair_gretil_svarita_leaks_in_vp(vp, pp_text=pp)
  assert n_fx == 7
  assert "पृञ्चती᳓र्म᳓धुना प᳓यः ॥" in fixed
  assert "व्य᳙हं᳓" in fixed and "कन्या᳙नां" in fixed and "तन्वं᳙" in fixed and "सो᳙ ऽयं" in fixed
  assert "ध्रुवा᳓यां ।\nशं᳓ ते ।\nकृणो᳓मि ।\nजानीहि ॥" in fixed
  assert "ते᳓षा᳓ं च ते ।\nनै᳓नम् ॥" in fixed

  # Genuine mid-line yaṇ / praśliṣṭa / kampa preserved
  vp_vsk = "त᳓व श᳓रीरं पतयिष्ण्व् अ᳙र्वन्त᳓व । ते᳓न ग᳙मेम । द्यौ᳙र् आसीत् ।\nअँ᳙होमु᳓चः ॥"
  pp_vsk = "तव॑। श॒रीर॑म्। प॒त॒यि॒ष्णु। अ॒र्वन्त॑वत्। तेन॑। व॒यम्। ग॒मे॒म॒। द्यौः। आ॒सी॒त्। अँ॒हो॒मुचः॑।"
  fixed_vsk, _ = repair_gretil_svarita_leaks_in_vp(vp_vsk, pp_text=pp_vsk)
  assert "पतयिष्ण्व् अ᳙र्वन्त᳓व" in fixed_vsk
  assert "ते᳓न गमेम" in fixed_vsk
  assert "द्यौ᳓र् आसीत्" in fixed_vsk
  assert "अँहोमु᳓चः ॥" in fixed_vsk

  # Tree repair preserves js_include blocks & frontmatter and propagates transitively
  hugo = tmp_path / "hugo"
  repo = hugo / "vedAH"
  vp_dir = repo / "static" / "atharva" / "shaunakam" / "vishvAsa-prastutiH" / "01"
  tk_dir = repo / "static" / "atharva" / "shaunakam" / "sarvASh_TIkAH" / "01"
  host_dir = repo / "content" / "atharva" / "paippalAdam"
  vp_dir.mkdir(parents=True)
  tk_dir.mkdir(parents=True)
  host_dir.mkdir(parents=True)

  src = vp_dir / "01.md"
  src.write_text('+++\ntitle = "०१"\n+++\nअम्ब᳓यो ।\nपृ᳙ञ्चती᳓ः ॥\n', encoding="utf-8")
  (tk_dir / "01.md").write_text(
    '<details><summary>पदपाठः</summary>\n\nअ॒म्बयः॑। पृ॒ञ्च॒तीः।\n</details>\n',
    encoding="utf-8",
  )
  host = host_dir / "01.md"
  host.write_text(
    '<div class="js_include" unfilled url="/vedAH/atharva/shaunakam/vishvAsa-prastutiH/01/01.md">\n'
    'अम्ब᳓यो ।\nपृ᳙ञ्चती᳓ः ॥\n</div>\n',
    encoding="utf-8",
  )
  res = repair_tree_svarita_leaks(
    [vp_dir], refresh_host_dirs=[host_dir], hugo_base_dir=str(hugo), dry_run=False
  )
  assert str(src) in res["changed_files"]
  assert "पृञ्चती᳓ः" in src.read_text(encoding="utf-8")
  assert "पृञ्चती᳓ः" in host.read_text(encoding="utf-8")

