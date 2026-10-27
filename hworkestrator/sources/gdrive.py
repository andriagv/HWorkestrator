"""Google Drive source: a minimal REST client (user OAuth refresh token — service accounts cannot upload into a
personal My Drive, so we act as the user) and the source functions list_items / overview / submit, plus folder()
for the upload-folder picker.

Expected layout: the course folder (DRIVE_ROOT_FOLDER_ID) holds the assignment FILES ("დავალება 3.pdf") and the
lecturer's upload folders ("4 დავ. მიმდინარე" → "<group>"); the user picks the upload folder in the chat."""
import json
import mimetypes
from pathlib import Path

import requests

from ..config import settings
from ..models import Overview, PipelineError
from .weeks import numbers_in

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
GDOC = "application/vnd.google-apps.document"
GSLIDES = "application/vnd.google-apps.presentation"
GFOLDER = "application/vnd.google-apps.folder"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
# Google-native files are exported; other google-apps types (forms, sheets...) cannot be downloaded
EXPORT = {GDOC: (DOCX, ".docx"), GSLIDES: (PPTX, ".pptx")}


def downloadable(f):
    return f["mimeType"] in EXPORT or not f["mimeType"].startswith("application/vnd.google-apps.")


class DriveError(RuntimeError):
    pass


class Drive:
    def __init__(self, client_id, client_secret, refresh_token, session=None):
        self.cid, self.secret, self.refresh = client_id, client_secret, refresh_token
        self.http = session or requests.Session()
        self._access = None

    def _headers(self):
        if self._access is None:
            r = self.http.post("https://oauth2.googleapis.com/token", data={
                "client_id": self.cid, "client_secret": self.secret,
                "refresh_token": self.refresh, "grant_type": "refresh_token"}, timeout=30)
            if r.status_code != 200:
                raise DriveError(f"Google auth failed: {r.text[:200]}")
            self._access = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._access}"}

    def _get(self, path, **params):
        r = self.http.get(f"{API}/{path}", headers=self._headers(), params=params, timeout=60)
        if r.status_code != 200:
            raise DriveError(f"Drive {path}: {r.status_code} {r.text[:200]}")
        return r

    def get(self, file_id):
        return self._get(f"files/{file_id}", fields="id,name,mimeType", supportsAllDrives="true").json()

    def children(self, parent_id, order=None):
        out, token = [], None
        while True:
            p = {"q": f"'{parent_id}' in parents and trashed=false", "pageSize": 200,
                 "fields": "nextPageToken, files(id,name,mimeType)",
                 "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if order:
                p["orderBy"] = order
            if token:
                p["pageToken"] = token
            j = self._get("files", **p).json()
            out += j["files"]
            token = j.get("nextPageToken")
            if not token:
                return out

    def download(self, f, dest_dir):
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if f["mimeType"] in EXPORT:
            mime, ext = EXPORT[f["mimeType"]]
            r = self._get(f"files/{f['id']}/export", mimeType=mime)
            path = dest_dir / (f["name"] + ext)
        else:
            r = self._get(f"files/{f['id']}", alt="media", supportsAllDrives="true")
            # a file uploaded without an extension ("დავალება 4") gets one from its type
            ext = "" if Path(f["name"]).suffix else (mimetypes.guess_extension(f["mimeType"]) or "")
            path = dest_dir / (f["name"] + ext)
        path.write_bytes(r.content)
        return path

    def upload(self, folder_id, path, name):
        """Upload into the folder; a file with the same name there is replaced (new version), not duplicated."""
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        same = [f for f in self.children(folder_id) if f["name"] == name and not f["mimeType"].startswith(
            "application/vnd.google-apps.")]
        meta = {"name": name} if same else {"name": name, "parents": [folder_id]}
        files = {"metadata": ("metadata", json.dumps(meta), "application/json; charset=UTF-8"),
                 "file": (name, path.read_bytes(), mime)}
        params = {"uploadType": "multipart", "supportsAllDrives": "true"}
        if same:
            r = self.http.patch(f"{UPLOAD}/{same[0]['id']}", headers=self._headers(), files=files,
                                params=params, timeout=180)
        else:
            r = self.http.post(UPLOAD, headers=self._headers(), files=files, params=params, timeout=180)
        if r.status_code != 200:
            raise DriveError(f"upload failed: {r.status_code} {r.text[:200]}")
        return r.json()["id"]


# ---------------------------------------------------------------- source functions
def client():
    if not (settings.google_client_id and settings.google_refresh_token and settings.drive_root_folder_id):
        raise PipelineError("Google Drive წვდომა არ არის მორგებული (GOOGLE_* ცვლადები)")
    return Drive(settings.google_client_id, settings.google_client_secret, settings.google_refresh_token)


def list_items(subject_key):
    """The assignment files of the course folder, newest first."""
    files = client().children(settings.drive_root_folder_id, order="createdTime desc")
    return [(f["name"], f["id"]) for f in files if not f["mimeType"].endswith("folder") and downloadable(f)]


def overview(subject_key, file_id, work):
    """One assignment file; its number comes from the file name. The upload folder is picked later (folder())."""
    drv = client()
    f = drv.get(file_id)
    path = drv.download(f, Path(work) / "src")
    nums = numbers_in(Path(f["name"]).stem)
    target = {"kind": "drive", "folder_id": None, "label": "Drive"}
    return Overview(subject_key, nums[0] if nums else 0, f["name"], f"📎 {path.name}", [path], "", [target],
                    number=str(nums[0]) if nums else Path(f["name"]).stem)


def folder(folder_id=None):
    """A folder for the upload picker: {"id", "name", "is_root", "folders": [(name, id)], "files": [names]}."""
    drv = client()
    root = settings.drive_root_folder_id
    folder_id = folder_id or root
    kids = drv.children(folder_id)
    return {"id": folder_id, "is_root": folder_id == root,
            "name": "" if folder_id == root else drv.get(folder_id)["name"],
            "folders": sorted((k["name"], k["id"]) for k in kids if k["mimeType"].endswith("folder")),
            "files": [k["name"] for k in kids if not k["mimeType"].endswith("folder")]}


def submit(target, path):
    if not target.get("folder_id"):
        raise PipelineError("აირჩიე Drive-ის საქაღალდე")
    client().upload(target["folder_id"], path, Path(path).name)
    return f"✅ ატვირთულია Drive-ზე: {target.get('label', '')}/{Path(path).name}"
