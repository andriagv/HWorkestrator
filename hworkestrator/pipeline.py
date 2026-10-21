"""prepare(): find the assignment, run the skill, return a Job. submit(): upload the approved result."""
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings
from .gdrive import Drive
from .moodle import Moodle, lecture_file_url
from .registry import SUBJECTS
from .runners import extract_text, html_to_text, run_cppwork, run_latexwork, result_name
from .weeks import int_to_roman, numbers_in, parse_week


class PipelineError(RuntimeError):
    pass


@dataclass
class Job:
    subject: str
    skill: str
    week: int
    label: str
    upload_file: Path                       # what gets uploaded
    extra_files: list = field(default_factory=list)   # also sent to Telegram (e.g. tex zip)
    target: dict = field(default_factory=dict)         # where to upload
    info: str = ""


def _require_profile():
    if not (settings.student_name and settings.student_group):
        raise PipelineError("STUDENT_NAME და STUDENT_GROUP უნდა იყოს მითითებული .env-ში")


def _moodle():
    if not settings.moodle_token:
        raise PipelineError("MOODLE_TOKEN არ არის მითითებული")
    return Moodle(settings.moodle_url, settings.moodle_token)


def _drive():
    if not (settings.google_client_id and settings.google_refresh_token and settings.drive_root_folder_id):
        raise PipelineError("Google Drive წვდომა არ არის მორგებული (GOOGLE_* ცვლადები)")
    return Drive(settings.google_client_id, settings.google_client_secret, settings.google_refresh_token)


def new_workdir():
    Path(settings.workdir).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=settings.workdir))


@dataclass
class Overview:
    title: str
    text: str                    # what to show in the chat
    files: list                  # local files to send (lecture, attachments)
    has_content: bool            # False -> "no assignment"


def list_weeks(subject_key):
    """Week numbers that exist for the subject."""
    subject = SUBJECTS[subject_key]
    if subject["source"] == "moodle":
        return _moodle().week_numbers(subject["match"])
    drv = _drive()
    return sorted({n for f in drv.children(settings.drive_root_folder_id)
                   if "დავალება" in f["name"] for n in numbers_in(f["name"])[:1]})


def overview(subject_key, week):
    """Look at the week and describe the assignment, without generating anything."""
    subject = SUBJECTS[subject_key]
    label = int_to_roman(week)
    work = new_workdir()
    if subject["source"] == "moodle":
        mdl = _moodle()
        w = mdl.week(subject["match"], week)
        a = w["assignment"]
        files, lines = [], []
        url, fname = lecture_file_url(w["lecture"])
        if url:
            files.append(mdl.download(url, work / fname))
            lines.append(f"📎 ლექცია: {fname}")
        intro = html_to_text(a.get("intro", "")) if a else ""
        if intro:
            lines.append("📝 დავალების ტექსტი:\n" + intro[:1500])
        for att in (a or {}).get("introattachments", []):
            files.append(mdl.download(att["fileurl"], work / att["filename"]))
            lines.append(f"📎 დანართი: {att['filename']}")
        has = bool(url or intro or (a or {}).get("introattachments"))
        title = f"{w['course']['fullname']} — {w['section'].get('name', label)}"
        if not has:
            msg = ("დავალების ადგილი არსებობს, მაგრამ მასალა (ლექცია/ტექსტი) ჯერ არ არის ატვირთული."
                   if a else "დავალება არ არის.")
            return Overview(title, msg, [], False)
        if a:
            ex = mdl.existing_files(a["id"])
            lines.append("📤 უკვე ატვირთულია: " + ", ".join(ex) if ex else "📤 ჯერ არაფერია ატვირთული")
        return Overview(title, "\n".join(lines), files, True)
    drv = _drive()
    items = [f for f in drv.children(settings.drive_root_folder_id)
             if "დავალება" in f["name"] and week in numbers_in(f["name"])]
    if not items:
        return Overview(f"დავალება {label}", "დავალება არ არის.", [], False)
    kids = [k for k in drv.children(items[0]["id"])
            if k["name"].strip() != settings.drive_student_folder and not k["mimeType"].endswith("folder")]
    files = [drv.download(k, work / "src") for k in kids]
    lines = [f"📎 {f.name}" for f in files]
    return Overview(items[0]["name"], "\n".join(lines) or "საქაღალდეში ფაილი არ არის.", files, bool(files))


def prepare(subject_key, skill, week):
    _require_profile()
    subject = SUBJECTS[subject_key]
    if isinstance(week, str):
        week = parse_week(week)
    if week is None:
        raise PipelineError("კვირის ნომერი ვერ გავიგე")
    label = int_to_roman(week)
    work = new_workdir()
    if subject["source"] == "moodle":
        return _prepare_moodle(subject_key, subject, skill, week, label, work)
    return _prepare_drive(subject_key, subject, skill, week, label, work)


def _finish(subject_key, skill, week, label, work, task_text=None, pptx=None, target=None, info=""):
    course = SUBJECTS[subject_key]["title"]
    if skill == "cppwork":
        if pptx is None:
            raise PipelineError("cppwork-ს სჭირდება ლექციის pptx ფაილი, ეს ვერ ვიპოვე")
        docx, log = run_cppwork(pptx, label, work, course)
        return Job(subject_key, skill, week, label, docx, [], target or {}, info + "\n" + log[-600:])
    if not task_text or len(task_text.strip()) < 20:
        raise PipelineError("დავალების ტექსტი ვერ ამოვიღე")
    pdf, zipped, log = run_latexwork(task_text, label, work, course)
    return Job(subject_key, skill, week, label, pdf, [zipped], target or {}, info)


def _prepare_moodle(subject_key, subject, skill, week, label, work):
    mdl = _moodle()
    w = mdl.week(subject["match"], week)
    info = f"{w['course']['fullname']} — {w['section'].get('name', '')}"
    assignment = w["assignment"]
    if assignment is None:
        raise PipelineError(f"{info}: დავალების (assign) მოდული ვერ ვიპოვე")
    target = {"kind": "moodle", "assignment_id": assignment["id"],
              "existing": mdl.existing_files(assignment["id"])}
    if skill == "cppwork":
        url, fname = lecture_file_url(w["lecture"])
        if not url or not fname.lower().endswith(".pptx"):
            raise PipelineError(f"{info}: Lecture pptx ვერ ვიპოვე (ნაპოვნია: {fname})")
        pptx = mdl.download(url, work / fname)
        return _finish(subject_key, skill, week, label, work, pptx=pptx, target=target, info=info)
    parts = [html_to_text(assignment.get("intro", ""))]
    for att in assignment.get("introattachments", []):
        p = mdl.download(att["fileurl"], work / att["filename"])
        try:
            parts.append(extract_text(p))
        except ValueError:
            pass
    return _finish(subject_key, skill, week, label, work, task_text="\n\n".join(parts), target=target, info=info)


def _prepare_drive(subject_key, subject, skill, week, label, work):
    drv = _drive()
    items = [f for f in drv.children(settings.drive_root_folder_id)
             if "დავალება" in f["name"] and week in numbers_in(f["name"])]
    if not items:
        raise PipelineError(f"Drive-ზე 'დავალება {week}' ვერ ვიპოვე")
    item = items[0]
    kids = drv.children(item["id"])
    student = [k for k in kids if k["name"].strip() == settings.drive_student_folder]
    if not student:
        raise PipelineError(f"'{item['name']}'-ში საქაღალდე '{settings.drive_student_folder}' ვერ ვიპოვე")
    files = [drv.download(k, work / "src") for k in kids
             if k["id"] != student[0]["id"] and not k["mimeType"].endswith("folder")]
    target = {"kind": "drive", "folder_id": student[0]["id"]}
    info = item["name"]
    if skill == "cppwork":
        pptx = next((f for f in files if f.suffix.lower() == ".pptx"), None)
        return _finish(subject_key, skill, week, label, work, pptx=pptx, target=target, info=info)
    texts = []
    for f in files:
        try:
            texts.append(extract_text(f))
        except ValueError:
            pass
    return _finish(subject_key, skill, week, label, work, task_text="\n\n".join(texts), target=target, info=info)


def submit(job):
    t = job.target
    if t.get("kind") == "moodle":
        _moodle().submit_file(t["assignment_id"], job.upload_file, finalize=settings.moodle_finalize)
        return "✅ ატვირთულია elearning-ზე" + (" და გაგზავნილია" if settings.moodle_finalize else " (შენახულია)")
    if t.get("kind") == "drive":
        _drive().upload(t["folder_id"], job.upload_file, job.upload_file.name)
        return f"✅ ატვირთულია Drive-ზე ({settings.drive_student_folder})"
    raise PipelineError("ატვირთვის მიზანი უცნობია")
