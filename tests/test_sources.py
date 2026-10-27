"""Sources: week parsing, the Moodle source (fake Moodle) and the Drive source (fake Drive / fake HTTP)."""

import pytest
from fakes import FILES, SECTIONS, FakeMoodle

from hworkestrator import pipeline
from hworkestrator.sources import gdrive
from hworkestrator.sources import moodle as moodle_src
from hworkestrator.sources.moodle import module_files
from hworkestrator.sources.weeks import find_week_section, int_to_roman, numbers_in, parse_week


# ---------------------------------------------------------------- weeks
def test_parse_week():
    assert [parse_week(x) for x in ("VI", "6", "კვირა 6", "iv", "Week 12")] == [6, 6, 6, 4, 12]
    assert parse_week("abc") is None
    assert int_to_roman(14) == "XIV"


def test_numbers_in():
    assert 6 in numbers_in("VI კვირა") and 10 in numbers_in("კვირა 10")


# ---------------------------------------------------------------- Moodle


def test_find_week_section_and_modules():
    s = find_week_section(SECTIONS, 4)
    assert s["name"] == "IV კვირა"
    assert module_files(s["modules"][0]) == [("https://x/pluginfile.php/1/a.pptx", "Lecture IV_struct.pptx")]
    assert find_week_section(SECTIONS, 9) is None


def test_week_lookup():
    w = FakeMoodle().week("სტრუქტურები და ალგორითმები", 4)
    assert [m["id"] for m in w["resources"]] == [111]
    assert [(i["module"]["id"], i["assignment"]["id"]) for i in w["assigns"]] == [(222, 999)]


def test_moodle_source_lists_weeks_and_targets(monkeypatch, tmp_path):
    fake = FakeMoodle()
    monkeypatch.setattr(moodle_src, "client", lambda: fake)
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    assert pipeline.list_items("dsa") == [("IV", "4"), ("V", "5")]
    ov = pipeline.overview("dsa", "4")
    assert [f.name for f in ov.files] == ["Lecture IV_struct.pptx"] and ov.label == "IV"
    assert ov.targets == [{"kind": "moodle", "assignment_id": 999, "label": "დავალება 4", "existing": ["old.docx"]}]


def test_week_with_several_assignments_lists_them_all(monkeypatch, tmp_path):
    """"დავალება" + "პრაქტიკული 4" + lecture: every activity is inspected, user later picks the target."""
    sections = [{"name": "IV კვირა", "section": 4, "modules": [
        {"id": 1, "modname": "assign", "name": "დავალება"},
        {"id": 2, "modname": "resource", "name": "ლექცია 4", "contents": [
            {"type": "file", "filename": "lec.docx", "fileurl": "https://x/pluginfile.php/a/lec.docx"}]},
        {"id": 3, "modname": "assign", "name": "პრაქტიკული 4"},
        {"id": 4, "modname": "folder", "name": "მასალა", "contents": [
            {"type": "file", "filename": "data.pdf", "fileurl": "https://x/pluginfile.php/a/data.pdf"}]},
        {"id": 5, "modname": "resource", "name": "hidden", "uservisible": False}]}]

    class Many(FakeMoodle):
        def call(self, fn, **p):
            if fn == "core_course_get_contents":
                return sections
            if fn == "mod_assign_get_assignments":
                return {"courses": [{"assignments": [
                    {"id": 10, "cmid": 1, "intro": ""},
                    {"id": 11, "cmid": 3, "intro": "<p>Practice task text</p>"}]}]}
            return super().call(fn, **p)

    monkeypatch.setattr(moodle_src, "client", lambda: Many())
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    ov = pipeline.overview("dsa", "4")
    assert sorted(f.name for f in ov.files) == ["data.pdf", "lec.docx"]       # hidden module skipped
    assert [t["label"] for t in ov.targets] == ["დავალება", "პრაქტიკული 4"]
    assert "Practice task text" in ov.intro and "პრაქტიკული 4" in ov.text


# ---------------------------------------------------------------- Google Drive


def test_drive_lists_assignment_files_and_folders(drive):
    assert pipeline.list_items("infosec") == [("დავალება 3.pdf", "f3"), ("დავალება 4", "f4")]   # no form, no folders
    ov = pipeline.overview("infosec", "f3")
    assert ov.label == "3" and [f.name for f in ov.files] == ["დავალება 3.txt"]
    assert pipeline.overview("infosec", "f4").label == "4"
    root = pipeline.drive_folder()
    assert root["is_root"] and [n for n, _ in root["folders"]] == ["3 დავალება", "4 დავ. მიმდინარე"]
    d3 = pipeline.drive_folder("d3")
    assert d3["name"] == "3 დავალება" and [n for n, _ in d3["folders"]] == ["000000-0", "111111-1"]


def test_drive_submit_needs_a_chosen_folder(drive, tmp_path):
    f = tmp_path / "დავალება 3 - X.pdf"
    f.write_bytes(b"%PDF")
    with pytest.raises(pipeline.PipelineError):
        gdrive.submit({"kind": "drive", "folder_id": None}, f)
    assert "000000-0" in gdrive.submit({"kind": "drive", "folder_id": "g1", "label": "000000-0"}, f)
    assert drive.uploaded == ("g1", "დავალება 3 - X.pdf")


def test_downloaded_file_without_extension_gets_one(tmp_path):
    class S:
        def get(self, url, **kw):
            return type("R", (), {"status_code": 200, "content": b"x", "json": lambda self: {}})()
    drv = gdrive.Drive("c", "s", "r", S())
    drv._access = "a"
    assert drv.download(FILES["f4"], tmp_path).name == "დავალება 4.docx"
    assert drv.download(FILES["f3"], tmp_path).name == "დავალება 3.pdf"


class Resp:
    status_code = 200

    def __init__(self, data=None):
        self.data = data or {}

    def json(self):
        return self.data


class Session:
    def __init__(self, existing):
        self.existing, self.sent = existing, []

    def post(self, url, **kw):
        self.sent.append(("POST", url, kw.get("params")))
        return Resp({"access_token": "a"} if "oauth2" in url else {"id": "new"})

    def patch(self, url, **kw):
        self.sent.append(("PATCH", url, kw.get("params")))
        return Resp({"id": url.rsplit("/", 1)[1]})

    def get(self, url, **kw):
        return Resp({"files": self.existing})


def test_upload_replaces_a_file_with_the_same_name(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"x")
    s = Session([{"id": "f1", "name": "დავალება 3 - X.pdf", "mimeType": "application/pdf"}])
    assert gdrive.Drive("c", "s", "r", s).upload("dir", f, "დავალება 3 - X.pdf") == "f1"
    assert s.sent[-1][0] == "PATCH"
    s = Session([])
    assert gdrive.Drive("c", "s", "r", s).upload("dir", f, "დავალება 3 - X.pdf") == "new"
    assert s.sent[-1][0] == "POST"
