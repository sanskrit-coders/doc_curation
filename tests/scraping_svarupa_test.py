import json
import unicodedata
from unittest import mock

import pytest
import requests

from doc_curation.scraping.misc_sites import svarupa
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva import shatapatha as kanva_sb


class _FakeResponse:
  def __init__(self, status_code: int, payload: dict, text: str = ""):
    self.status_code = status_code
    self._payload = payload
    self.ok = 200 <= status_code < 300
    self.text = text

  def json(self):
    return self._payload


def test_to_madhyandina_svara():
  src = "ॐ स वै॒ संभारान्त्सं॒भरति ॥१॥"
  assert svarupa.to_madhyandina_svara(src) == "ॐ स वै᳘ संभारान्त्सं᳘भरति ॥१॥"
  assert "\u0952" not in svarupa.to_madhyandina_svara(src)


def test_clean_overview_html_handles_paragraphs_breaks_and_entities():
  assert svarupa.clean_overview_html("<p>प्रथमकाण्डः</p>") == "प्रथमकाण्डः"
  assert svarupa.clean_overview_html("<p>First.</p><p>Second &amp; third.<br/>Line 2</p>") == (
    "First.\n\nSecond & third.\nLine 2"
  )
  assert svarupa.clean_overview_html(None) == ""


def test_extract_mantra_view_summary_and_commentary():
  raw_view = {
    "mantraIndex": "22.1.1.1.1",
    "displayIndex": "1.1.1.1",
    "language": [
      {
        "languageName": "English",
        "groups": [
          {
            "groupName": "context_and_interpretation",
            "groupContent": [
              {"name": "bhavartha", "value": [{"data": [{"value": "ignored bhavartha"}]}]},
              {
                "name": "commentary",
                "value": [
                  {
                    "mahatmaId": "556",
                    "mahatmaName": " C R Swaminathan ",
                    "data": [
                      {
                        "key": None,
                        "source": "TippaniSource",
                        "value": "<p>He gathers the requisite materials.</p>",
                        "audios": [{"audioPath": "skip.mp3"}],
                      }
                    ],
                  }
                ],
              },
            ],
          }
        ],
      }
    ],
  }
  summary = svarupa.extract_mantra_view_summary(raw_view)
  assert summary is not None
  assert "audios" not in json.dumps(summary)
  blocks = svarupa.extract_commentary_blocks(summary, language="English", preferred_mahatma="C R Swaminathan")
  assert blocks == [("C R Swaminathan", "He gathers the requisite materials.")]


def test_svarupa_client_refreshes_on_401_including_final_attempt_and_rotates_refresh():
  session = mock.MagicMock(spec=requests.Session)
  session.get.side_effect = [
    _FakeResponse(503, {}, "temp"),
    _FakeResponse(401, {"statusCode": "T1000"}),
    _FakeResponse(200, {"overView": "<p>ok</p>"}),
  ]
  session.post.return_value = _FakeResponse(200, {"token": "new-tok", "refreshToken": "new-ref"})
  client = svarupa.SvarupaClient("old-tok", "ref-tok", session=session, max_retries=2)

  with mock.patch.object(svarupa.time, "sleep"):
    ov = client.fetch_overview("22")
  assert ov == {"overView": "<p>ok</p>"}
  assert client.auth_token == "new-tok"
  assert client.refresh_token == "new-ref"
  assert session.get.call_args_list[2].kwargs["headers"]["Authorization"] == "Bearer new-tok"


def test_svarupa_client_fails_fast_on_404_and_401_without_refresh():
  session = mock.MagicMock(spec=requests.Session)
  session.get.return_value = _FakeResponse(404, {}, "not found")
  client = svarupa.SvarupaClient("tok", session=session, max_retries=3)
  with pytest.raises(RuntimeError, match="HTTP 404"):
    client.fetch_overview("22")
  assert session.get.call_count == 1

  session.reset_mock()
  session.get.return_value = _FakeResponse(401, {"statusCode": "T1000"})
  with pytest.raises(RuntimeError, match="401"):
    client.fetch_overview("22")


def test_svarupa_client_walk_tree_and_fetch_many_views():
  session = mock.MagicMock(spec=requests.Session)

  def fake_get(url, headers=None, timeout=None):
    if url.endswith("/scripture/tree/overview/22"):
      return _FakeResponse(200, {"overView": "root"})
    if url.endswith("/scripture/tree/levelInfo/22"):
      return _FakeResponse(
        200,
        {"levelInfo": [{"levels": [{"hierarchyIndex": "22.1", "order": 1, "type": "Ekapātkāṇḍam", "last": False}]}]},
      )
    if url.endswith("/scripture/tree/overview/22.1"):
      return _FakeResponse(200, {"overView": "<p>k1</p>"})
    if url.endswith("/scripture/tree/levelInfo/22.1"):
      return _FakeResponse(
        200,
        {"levelInfo": [{"levels": [{"hierarchyIndex": "22.1.1", "order": 1, "type": "Adhyāyaḥ", "last": True}]}]},
      )
    if url.endswith("/scripture/tree/overview/22.1.1"):
      return _FakeResponse(200, {"overView": ""})
    if url.endswith("/scripture/tree/all/mantras/22.1.1"):
      return _FakeResponse(200, {"mantraList": [{"mantraIndex": "22.1.1.1", "language": []}]})
    if url.endswith("/scripture/tree/view/mantra/22.1.1.1"):
      return _FakeResponse(200, {"mantraIndex": "22.1.1.1", "language": []})
    if url.endswith("/scripture/tree/view/mantra/22.1.1.2"):
      return _FakeResponse(404, {}, "missing")
    raise AssertionError(f"Unexpected URL: {url}")

  session.get.side_effect = fake_get
  client = svarupa.SvarupaClient("tok", session=session, max_retries=1)
  tree, overviews, mantras = client.fetch_tree_and_mantras(22, max_workers=2)
  assert len(tree) == 1
  assert tree[0]["_children"][0]["hierarchyIndex"] == "22.1.1"
  assert overviews["22.1"]["overView"] == "<p>k1</p>"
  assert len(mantras["22.1.1"]) == 1

  progress = []
  views = client.fetch_many_mantra_views(
    ["22.1.1.1", "22.1.1.2"],
    max_workers=2,
    on_progress=lambda d, tot: progress.append((d, tot)),
  )
  assert views["22.1.1.1"] is not None
  assert views["22.1.1.2"] is None
  assert sorted(progress) == [(1, 2), (2, 2)]

  with pytest.raises(RuntimeError, match="1/2 mantra views"):
    client.fetch_many_mantra_views(["22.1.1.1", "22.1.1.2"], max_workers=2, raise_on_error=True)


def test_extract_tokens_from_chrome_profile_cleans_up_on_driver_error(tmp_path):
  src_prof = tmp_path / "chrome"
  (src_prof / "Default" / "Local Storage").mkdir(parents=True)
  scratch_prof = tmp_path / "scratch_prof"

  with mock.patch("selenium.webdriver.Chrome", side_effect=RuntimeError("boom")):
    with pytest.raises(RuntimeError, match="boom"):
      svarupa.extract_tokens_from_chrome_profile(
        chrome_user_data_dir=src_prof,
        scratch_profile_dir=scratch_prof,
      )
  assert not scratch_prof.exists()


def test_build_kanva_sarva_prastuti_sorted_idempotent_nfd_and_anomalies(tmp_path):
  # Provide NFD IAST name and unsorted adhyaya/brahmana/kandika order with gaps and anomalies.
  nfd_name = unicodedata.normalize("NFD", "Ekapātkāṇḍam")
  tree = [
    {
      "hierarchyIndex": "22.2",
      "order": 2,
      "type": nfd_name,
      "_children": [
        {
          "hierarchyIndex": "22.2.2",
          "order": 2,
          "_children": [
            {"hierarchyIndex": "22.2.2.3", "order": 3, "last": True},
            {"hierarchyIndex": "22.2.2.1", "order": 1, "last": True},
          ],
        }
      ],
    }
  ]
  overviews = {
    "22": {"overView": "<p>Root overview.</p><p>Second paragraph.</p>"},
    "22.2": {"overView": "<p>द्वितीयकाण्डः</p>"},
  }
  mantras_by_leaf = {
    "22.2.2.3": [
      {
        "mantraIndex": "22.2.2.3.3",
        "displayIndex": "2.2.3.3",
        "language": [{"languageName": "Sanskrit", "vedamanatra": "अ॒थ` ॥३॥"}],
      },
      {
        "mantraIndex": "22.2.2.3.1",
        "displayIndex": "2.2.3.1",
        "language": [{"languageName": "Sanskrit", "vedamanatra": "स वै॒ वर्त॑ते ॥१॥"}],
      },
    ],
    "22.2.2.1": [],
  }
  views_by_id = {
    "22.2.2.3.1": {
      "languages": {
        "English": {
          "commentary": [{"mahatmaName": "C R Swaminathan", "data": [{"value": "Verily he."}]}]
        }
      }
    }
  }

  stats = kanva_sb.build_sarva_prastuti(
    tree,
    overviews,
    mantras_by_leaf,
    dest_root=tmp_path,
    views_by_id=views_by_id,
  )
  # Second run verifies file_list.md is idempotent (doesn't include itself).
  kanva_sb.build_sarva_prastuti(
    tree,
    overviews,
    mantras_by_leaf,
    dest_root=tmp_path,
    views_by_id=views_by_id,
  )

  assert stats["files_written"] == 2
  assert stats["kandikas_written"] == 2
  assert stats["commentaries_written"] == 1
  assert len(stats["anomalies_udatta"]) == 1
  assert len(stats["anomalies_backtick"]) == 1

  md_path = tmp_path / "02_ekapAtkANDam" / "02" / "3.md"
  assert md_path.exists()
  txt = md_path.read_text(encoding="utf-8")
  assert txt.index("## ०१") < txt.index("## ०३")
  assert "स वै᳘ वर्त॑ते ॥१॥" in txt
  assert "<details><summary>C R Swaminathan</summary>\n\nVerily he.\n</details>" in txt
  assert "\u0952" not in txt

  k_idx = (tmp_path / "02_ekapAtkANDam" / "_index.md").read_text(encoding="utf-8")
  assert 'title = "+०२ एकपात्काण्डम्"' in k_idx

  root_idx = (tmp_path / "_index.md").read_text(encoding="utf-8")
  assert "Root overview.\n\nSecond paragraph." in root_idx
  assert "Kāṇḍa 1" in root_idx
  assert "Adhyāya 2.1" in root_idx
  assert "Brāhmaṇa 2.2.2" in root_idx
  assert "Empty Brāhmaṇa 2.2.1" in root_idx
  assert "Kaṇḍikā 2.2.3.2" in root_idx

  fl = (tmp_path / "file_list.md").read_text(encoding="utf-8")
  assert "/file_list.md" not in fl


def test_load_views_dir_and_download_and_build(tmp_path):
  vdir = tmp_path / "views"
  vdir.mkdir()
  (vdir / "k01.json").write_text(json.dumps({"22.1.1.1.1": {"languages": {}}}), encoding="utf-8")
  (vdir / "k02.json").write_text(json.dumps({"22.2.1.1.1": {"languages": {}}}), encoding="utf-8")
  assert set(kanva_sb.load_views_dir(vdir).keys()) == {"22.1.1.1.1", "22.2.1.1.1"}
  assert kanva_sb.load_views_dir(tmp_path / "nonexistent") == {}

  fake_client = mock.MagicMock()
  fake_client.fetch_tree_and_mantras.return_value = (
    [
      {
        "hierarchyIndex": "22.1",
        "order": 1,
        "type": "Ekapātkāṇḍam",
        "_children": [
          {"hierarchyIndex": "22.1.1", "order": 1, "_children": [{"hierarchyIndex": "22.1.1.1", "order": 1, "last": True}]}
        ],
      },
      {
        "hierarchyIndex": "22.17",
        "order": 17,
        "type": "Bṛhadāraṇyakam",
        "_children": [],
      },
    ],
    {"22": {"overView": "ov"}},
    {"22.1.1.1": [{"mantraIndex": "22.1.1.1.1", "language": [{"languageName": "Sanskrit", "vedamanatra": "स वै॒ ॥१॥"}]}]},
  )
  fake_client.fetch_many_mantra_views.return_value = {
    "22.1.1.1.1": {
      "languages": {"English": {"commentary": [{"mahatmaName": "C R Swaminathan", "data": [{"value": "He."}]}]}}
    }
  }
  with mock.patch.object(svarupa, "extract_tokens_from_chrome_profile", return_value={"authToken": "t"}), \
      mock.patch.object(svarupa, "SvarupaClient", return_value=fake_client):
    stats = kanva_sb.download_and_build(
      scratch_profile_dir=tmp_path / "prof",
      dest_root=tmp_path / "out",
      views_cache_dir=tmp_path / "cache",
    )
  assert stats["commentaries_written"] == 1
  assert (tmp_path / "cache" / "k01.json").exists()
  assert not (tmp_path / "cache" / "k17.json").exists()
