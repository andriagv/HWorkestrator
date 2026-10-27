"""Fake Moodle and Google Drive used by the tests (no network, no real accounts)."""
from pathlib import Path

from hworkestrator.sources import gdrive
from hworkestrator.sources.moodle import Moodle

SECTIONS = [
    {"name": "General", "section": 0, "modules": []},
    {"name": "IV კვირა", "section": 4, "modules": [
        {"id": 111, "modname": "resource", "name": "Lecture IV",
         "contents": [{"type": "file", "filename": "Lecture IV_struct.pptx",
                       "fileurl": "https://x/pluginfile.php/1/a.pptx"}]},
        {"id": 222, "modname": "assign", "name": "დავალება 4"}]},
    {"name": "V კვირა", "section": 5, "modules": []},
]



class FakeMoodle(Moodle):
    """Answers the web-service calls from SECTIONS; downloads write a stub (or `lecture`) file."""
    def __init__(self, lecture=None):
        super().__init__("https://x", "T")
        self.submitted, self.lecture = None, lecture

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
        Path(dest).write_bytes(self.lecture.read_bytes() if self.lecture else b"x")
        return Path(dest)

    def submit_file(self, assignment_id, path, finalize=False):
        self.submitted = (assignment_id, Path(path).name)



FILES = {
    "f3": {"id": "f3", "name": "დავალება 3.pdf", "mimeType": "application/pdf"},
    "f4": {"id": "f4", "name": "დავალება 4", "mimeType": gdrive.DOCX},          # uploaded without extension
    "form": {"id": "form", "name": "გამოკითხვა", "mimeType": "application/vnd.google-apps.form"},
}
FOLDERS = {
    "root": [FILES["f3"], FILES["f4"], FILES["form"],
             {"id": "d4", "name": "4 დავ. მიმდინარე", "mimeType": gdrive.GFOLDER},
             {"id": "d3", "name": "3 დავალება", "mimeType": gdrive.GFOLDER}],
    "d3": [{"id": "g1", "name": "000000-0", "mimeType": gdrive.GFOLDER},
           {"id": "g2", "name": "111111-1", "mimeType": gdrive.GFOLDER}],
    "g1": [{"id": "x", "name": "old.pdf", "mimeType": "application/pdf"}],
}
NAMES = {"d3": "3 დავალება", "d4": "4 დავ. მიმდინარე", "g1": "000000-0", **{k: v["name"] for k, v in FILES.items()}}
TASK = "ამოცანა 1. დაშიფრეთ HELLO ცეზარის მეთოდით (k = 3).\nამოცანა 2. რა არის CIA ტრიადა?"


class FakeDrive(gdrive.Drive):
    """The course folder above; downloads write TASK as text; uploads are recorded."""
    def __init__(self):
        super().__init__("cid", "s", "r")
        self.uploaded = None

    def children(self, parent_id, order=None):
        return FOLDERS[parent_id]

    def get(self, file_id):
        return FILES.get(file_id) or {"id": file_id, "name": NAMES[file_id], "mimeType": gdrive.GFOLDER}

    def download(self, f, dest_dir):
        assert gdrive.downloadable(f)
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        path = Path(dest_dir) / (Path(f["name"]).stem + ".txt")
        path.write_text(TASK, encoding="utf8")
        return path

    def upload(self, folder_id, path, name):
        self.uploaded = (folder_id, name)

