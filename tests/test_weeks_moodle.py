import shutil
from pathlib import Path

import pytest

from hworkestrator import pipeline
from hworkestrator.moodle import Moodle, pick_assign, pick_lecture
from hworkestrator.weeks import find_week_section, int_to_roman, numbers_in, parse_week

LECTURE = Path.home() / "Downloads" / "Lecture IV_struct.pptx"


def test_parse_week():
    assert [parse_week(x) for x in ("VI", "6", "კვირა 6", "iv", "Week 12")] == [6, 6, 6, 4, 12]
    assert parse_week("abc") is None
    assert int_to_roman(14) == "XIV"


def test_numbers_in():
    assert 6 in numbers_in("VI კვირა") and 10 in numbers_in("კვირა 10")


SECTIONS = [
    {"name": "General", "section": 0, "modules": []},
    {"name": "IV კვირა", "section": 4, "modules": [
        {"id": 111, "modname": "resource", "name": "Lecture IV",
         "contents": [{"type": "file", "filename": "Lecture IV_struct.pptx",
                       "fileurl": "https://x/pluginfile.php/1/a.pptx"}]},
        {"id": 222, "modname": "assign", "name": "დავალება 4"}]},
    {"name": "V კვირა", "section": 5, "modules": []},
]


def test_find_week_section_and_modules():
    s = find_week_section(SECTIONS, 4)
    assert s["name"] == "IV კვირა"
    assert pick_lecture(s["modules"])["id"] == 111
    assert pick_assign(s["modules"])["id"] == 222
    assert find_week_section(SECTIONS, 9) is None


class FakeMoodle(Moodle):
    def __init__(self):
        super().__init__("https://x", "T")
        self.submitted = None

    def call(self, fn, **p):
        return {
            "core_webservice_get_site_info": {"userid": 7},
            "core_enrol_get_users_courses": [{"id": 5, "fullname": "მონაცემთა სტრუქტურები და ალგორითმები",
                                              "shortname": "DSA"}],
            "core_course_get_contents": SECTIONS,
            "mod_assign_get_submission_status": {"lastattempt": {"submission": {"plugins": [
                {"fileareas": [{"files": [{"filename": "old.docx"}]}]}]}}},
            "mod_assign_get_assignments": {"courses": [{"assignments": [
                {"id": 999, "cmid": 222, "intro": "<p>x</p>"}]}]},
        }[fn]

    def download(self, url, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(LECTURE, dest)
        return Path(dest)

    def submit_file(self, assignment_id, path, finalize=False):
        self.submitted = (assignment_id, Path(path).name)


def test_week_lookup():
    w = FakeMoodle().week("სტრუქტურები და ალგორითმები", 4)
    assert w["assignment"]["id"] == 999 and w["lecture"]["id"] == 111


@pytest.mark.skipif(not LECTURE.exists(), reason="sample lecture not available")
def test_cppwork_moodle_end_to_end(monkeypatch, tmp_path):
    fake = FakeMoodle()
    monkeypatch.setattr(pipeline, "_moodle", lambda: fake)
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    job = pipeline.prepare("dsa", "cppwork", "IV")
    assert job.upload_file.suffix == ".docx" and job.upload_file.exists()
    assert job.target == {"kind": "moodle", "assignment_id": 999, "existing": ["old.docx"]}
    monkeypatch.setattr(pipeline.settings.__class__, "moodle_finalize", False, raising=False)
    pipeline.submit(job)
    assert fake.submitted == (999, "დავალება IV - Test Student.docx")
