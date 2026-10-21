"""Moodle (elearning.gtu.ge) web-service client — token based, no browser."""
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

from .weeks import find_week_section, week_sections


class MoodleError(RuntimeError):
    pass


class Moodle:
    def __init__(self, url, token, session=None):
        self.url, self.token = url.rstrip("/"), token
        self.http = session or requests.Session()
        self._userid = None

    # --- low level ---
    def call(self, wsfunction, **params):
        data = {"wstoken": self.token, "wsfunction": wsfunction, "moodlewsrestformat": "json", **params}
        r = self.http.post(f"{self.url}/webservice/rest/server.php", data=data, timeout=60)
        r.raise_for_status()
        out = r.json()
        if isinstance(out, dict) and ("exception" in out or "errorcode" in out):
            raise MoodleError(f"{wsfunction}: {out.get('message') or out.get('error')} ({out.get('errorcode')})")
        return out

    def _with_token(self, fileurl):
        parts = urlparse(fileurl)
        q = dict(parse_qsl(parts.query))
        q["token"] = self.token
        # pluginfile.php -> webservice/pluginfile.php so the token is accepted
        path = parts.path.replace("/pluginfile.php", "/webservice/pluginfile.php") \
            if "/webservice/" not in parts.path else parts.path
        return urlunparse(parts._replace(path=path, query=urlencode(q)))

    # --- reading ---
    def userid(self):
        if self._userid is None:
            self._userid = self.call("core_webservice_get_site_info")["userid"]
        return self._userid

    def courses(self):
        return self.call("core_enrol_get_users_courses", userid=self.userid())

    def find_course(self, match):
        m = match.lower()
        hits = [c for c in self.courses()
                if m in c.get("fullname", "").lower() or m in c.get("shortname", "").lower()]
        if not hits:
            raise MoodleError(f"კურსი ვერ ვიპოვე: '{match}'")
        return hits[0]

    def contents(self, courseid):
        return self.call("core_course_get_contents", courseid=courseid)

    def week_numbers(self, course_match):
        course = self.find_course(course_match)
        return [n for n, _ in week_sections(self.contents(course["id"]))]

    def week(self, course_match, week):
        """-> dict(course, section, resources[module], assigns[{module, assignment}]).
        `resources` = every file/folder activity of the week; `assigns` = every assignment activity
        (e.g. "დავალება", "პრაქტიკული 4") with its details (text, attachments, id)."""
        course = self.find_course(course_match)
        section = find_week_section(self.contents(course["id"]), week)
        if section is None:
            raise MoodleError(f"{week}-ე კვირა ვერ ვიპოვე კურსში '{course['fullname']}'")
        mods = [m for m in section.get("modules", []) if m.get("uservisible", True)]
        data = self.call("mod_assign_get_assignments", **{"courseids[0]": course["id"]})
        by_cmid = {a["cmid"]: a for c in data.get("courses", []) for a in c.get("assignments", [])}
        return {
            "course": course, "section": section,
            "resources": [m for m in mods if m.get("modname") in ("resource", "folder")],
            "assigns": [{"module": m, "assignment": by_cmid.get(m["id"])}
                        for m in mods if m.get("modname") == "assign"],
        }

    def download(self, fileurl, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = self.http.get(self._with_token(fileurl), timeout=120)
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("application/json"):
            raise MoodleError(f"download failed: {r.text[:200]}")
        dest.write_bytes(r.content)
        return dest

    def existing_files(self, assignment_id):
        """Names of files already in the current submission (a new upload REPLACES them)."""
        st = self.call("mod_assign_get_submission_status", assignid=assignment_id)
        sub = (st.get("lastattempt") or {}).get("submission") or {}
        return [f["filename"] for p in sub.get("plugins", []) for fa in p.get("fileareas", [])
                for f in fa.get("files", [])]

    # --- writing ---
    def submit_file(self, assignment_id, path, finalize=False):
        """Upload a file into the user draft area and save it as the assignment submission."""
        path = Path(path)
        with open(path, "rb") as f:
            r = self.http.post(f"{self.url}/webservice/upload.php",
                               data={"token": self.token, "filearea": "draft", "itemid": 0},
                               files={"file_1": (path.name, f)}, timeout=180)
        r.raise_for_status()
        up = r.json()
        if isinstance(up, dict) and up.get("error"):
            raise MoodleError(f"upload: {up['error']}")
        itemid = up[0]["itemid"]
        warnings = self.call("mod_assign_save_submission", assignmentid=assignment_id,
                             **{"plugindata[files_filemanager]": itemid})
        if warnings:
            raise MoodleError(f"save_submission: {warnings}")
        if finalize:
            self.call("mod_assign_submit_for_grading", assignmentid=assignment_id,
                      acceptsubmissionstatement=1)
        return itemid


def module_files(module):
    """[(fileurl, filename)] of a file/folder activity."""
    return [(c["fileurl"], c["filename"]) for c in (module or {}).get("contents", [])
            if c.get("type") == "file"]
