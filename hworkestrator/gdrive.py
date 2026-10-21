"""Minimal Google Drive client (REST, user OAuth refresh token — service accounts cannot
upload into a personal My Drive, so we act as the user)."""
import mimetypes
from pathlib import Path

import requests

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
GDOC = "application/vnd.google-apps.document"
GFOLDER = "application/vnd.google-apps.folder"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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

    def children(self, parent_id):
        out, token = [], None
        while True:
            p = {"q": f"'{parent_id}' in parents and trashed=false", "pageSize": 200,
                 "fields": "nextPageToken, files(id,name,mimeType)",
                 "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
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
        if f["mimeType"] == GDOC:
            r = self._get(f"files/{f['id']}/export", mimeType=DOCX)
            path = dest_dir / (f["name"] + ".docx")
        else:
            r = self._get(f"files/{f['id']}", alt="media", supportsAllDrives="true")
            path = dest_dir / f["name"]
        path.write_bytes(r.content)
        return path

    def upload(self, folder_id, path, name):
        path = Path(path)
        meta = {"name": name, "parents": [folder_id]}
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files = {"metadata": ("metadata", __import__("json").dumps(meta), "application/json; charset=UTF-8"),
                 "file": (name, path.read_bytes(), mime)}
        r = self.http.post(UPLOAD, headers=self._headers(), files=files,
                           params={"uploadType": "multipart", "supportsAllDrives": "true"}, timeout=180)
        if r.status_code != 200:
            raise DriveError(f"upload failed: {r.status_code} {r.text[:200]}")
        return r.json()["id"]
