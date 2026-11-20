import json
from unittest import mock

import requests

from doc_curation.scraping.misc_sites import svarupa
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva import shatapatha as kanva_sb


class _FakeResponse:
  def __init__(self, status_code: int, payload: dict):
    self.status_code = status_code
    self._payload = payload
    self.ok = 200 <= status_code < 300

  def json(self):
    return self._payload


def test_to_madhyandina_svara():
  src = "ॐ स वै॒ संभारान्त्सं॒भरति ॥१॥"
  assert svarupa.to_madhyandina_svara(src) == "ॐ स वै᳘ संभारान्त्सं᳘भरति ॥१॥"
  assert "\u0952" not in svarupa.to_madhyandina_svara(src)


def test_clean_overview_html():
  assert svarupa.clean_overview_html("<p>प्रथमकाण्डः</p>") == "प्रथमकाण्डः"
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
              {
                "name": "bhavartha",
                "value": [{"data": [{"value": "ignored bhavartha"}]}],
              },
              {
                "name": "commentary",
                "value": [
                  {
                    "mahatmaId": "556",
                    "mahatmaName": "C R Swaminathan",
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


def test_svarupa_client_refreshes_on_401():
  session = mock.MagicMock(spec=requests.Session)
  session.get.side_effect = [
    _FakeResponse(401, {"statusCode": "T1000"}),
    _FakeResponse(200, {"overView": "<p>ok</p>"}),
  ]
  session.post.return_value = _FakeResponse(200, {"token": "new-tok"})
  client = svarupa.SvarupaClient("old-tok", "ref-tok", session=session)

  ov = client.fetch_overview("22")
  assert ov == {"overView": "<p>ok</p>"}
  assert client.auth_token == "new-tok"
  session.post.assert_called_once()
  assert session.get.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer new-tok"


def test_svarupa_client_walk_tree():
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
    raise AssertionError(f"Unexpected URL: {url}")

  session.get.side_effect = fake_get
  client = svarupa.SvarupaClient("tok", session=session)
  tree, overviews, mantras = client.fetch_tree_and_mantras(22, max_workers=2)
  assert len(tree) == 1
  assert tree[0]["_children"][0]["hierarchyIndex"] == "22.1.1"
  assert overviews["22.1"]["overView"] == "<p>k1</p>"
  assert len(mantras["22.1.1"]) == 1


def test_build_kanva_sarva_prastuti_with_gaps_and_commentary(tmp_path):
  tree = [
    {
      "hierarchyIndex": "22.1",
      "order": 1,
      "type": "Ekapātkāṇḍam",
      "_children": [
        {
          "hierarchyIndex": "22.1.2",
          "order": 2,
          "_children": [
            {"hierarchyIndex": "22.1.2.3", "order": 3, "last": True},
          ],
        }
      ],
    }
  ]
  overviews = {
    "22": {"overView": "Root overview"},
    "22.1": {"overView": "<p>प्रथमकाण्डः</p>"},
  }
  mantras_by_leaf = {
    "22.1.2.3": [
      {
        "mantraIndex": "22.1.2.3.1",
        "displayIndex": "1.2.3.1",
        "language": [{"languageName": "Sanskrit", "vedamanatra": "स वै॒ ॥१॥"}],
      },
      {
        "mantraIndex": "22.1.2.3.3",
        "displayIndex": "1.2.3.3",
        "language": [{"languageName": "Sanskrit", "vedamanatra": "अ॒थ` ॥३॥"}],
      },
    ]
  }
  views_by_id = {
    "22.1.2.3.1": {
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
  assert stats["files_written"] == 1
  assert stats["kandikas_written"] == 2
  assert stats["commentaries_written"] == 1

  md_path = tmp_path / "01_ekapAtkANDam" / "02" / "3.md"
  assert md_path.exists()
  txt = md_path.read_text(encoding="utf-8")
  assert 'title = "३"' in txt
  assert "## ०१" in txt and "## ०३" in txt
  assert "स वै᳘ ॥१॥" in txt
  assert "<details><summary>C R Swaminathan</summary>\n\nVerily he.\n</details>" in txt
  assert "\u0952" not in txt

  root_idx = (tmp_path / "_index.md").read_text(encoding="utf-8")
  assert "Adhyāya 1.1" in root_idx
  assert "Brāhmaṇa 1.2.1" in root_idx
  assert "Kaṇḍikā 1.2.3.2" in root_idx
  assert "01_ekapAtkANDam/02/3.md" in root_idx
  assert (tmp_path / "file_list.md").exists()


def test_load_views_dir_merges_kanda_files(tmp_path):
  (tmp_path / "k01.json").write_text(json.dumps({"22.1.1.1.1": {"a": 1}}), encoding="utf-8")
  (tmp_path / "k02.json").write_text(json.dumps({"22.2.1.1.1": {"a": 2}}), encoding="utf-8")
  merged = kanva_sb.load_views_dir(tmp_path)
  assert merged == {"22.1.1.1.1": {"a": 1}, "22.2.1.1.1": {"a": 2}}

