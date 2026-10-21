"""overview(): look at a week. prepare(): run a skill on the chosen source file(s). submit(): upload."""
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import pricing
from .config import settings
from .gdrive import Drive
from .moodle import Moodle, module_files
from .registry import SUBJECTS
from .runners import (extract_text, html_to_text, run_cppwork, run_jupiterwork,
                      run_latexwork)
from .weeks import int_to_roman, numbers_in


class PipelineError(RuntimeError):
    pass


@dataclass
class Overview:
    subject: str
    week: int
    title: str
    text: str                                         # what to show in the chat
    files: list = field(default_factory=list)         # local source files (lecture, attachments...)
    intro: str = ""                                   # assignment text written on the page
    targets: list = field(default_factory=list)       # upload places (one per assignment activity)
    has_content: bool = True                          # False -> "no assignment"

    @property
    def label(self):
        return int_to_roman(self.week)


@dataclass
class Job:
    subject: str
    skill: str
    week: int
    label: str
    upload_file: Path                                 # what gets uploaded
    extra_files: list = field(default_factory=list)   # also sent to Telegram (e.g. tex zip)
    target: dict = field(default_factory=dict)        # chosen upload place
    info: str = ""
    targets: list = field(default_factory=list)       # all possible upload places
    cost_note: str = ""                               # real token usage / cost of the run


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


# ---------------------------------------------------------------- looking at a week
def list_weeks(subject_key):
    """Week numbers that exist for the subject."""
    subject = SUBJECTS[subject_key]
    if subject["source"] == "moodle":
        return _moodle().week_numbers(subject["match"])
    drv = _drive()
    return sorted({n for f in drv.children(settings.drive_root_folder_id)
                   if "დავალება" in f["name"] for n in numbers_in(f["name"])[:1]})


def overview(subject_key, week):
    """Describe the week (lecture, text, attachments, what is already uploaded) without generating."""
    subject = SUBJECTS[subject_key]
    label = int_to_roman(week)
    work = new_workdir()
    if subject["source"] == "moodle":
        mdl = _moodle()
        w = mdl.week(subject["match"], week)
        files, lines, intros, targets = [], [], [], []
        for m in w["resources"]:                          # every lecture/file/folder of the week
            for url, fname in module_files(m):
                files.append(mdl.download(url, work / str(m["id"]) / fname))
                lines.append(f"📎 {m['name']}: {fname}")
        for item in w["assigns"]:                         # every assignment activity of the week
            m, a = item["module"], item["assignment"]
            lines.append(f"📌 {m['name']}")
            if not a:
                continue
            intro = html_to_text(a.get("intro", ""))
            if intro:
                lines.append("   📝 " + intro[:800])
                intros.append(f"{m['name']}:\n{intro}")
            for att in a.get("introattachments", []):
                files.append(mdl.download(att["fileurl"], work / f"a{m['id']}" / att["filename"]))
                lines.append(f"   📎 {att['filename']}")
            ex = mdl.existing_files(a["id"])
            lines.append("   📤 უკვე ატვირთულია: " + ", ".join(ex) if ex else "   📤 ჯერ არაფერია ატვირთული")
            targets.append({"kind": "moodle", "assignment_id": a["id"], "label": m["name"], "existing": ex})
        title = f"{w['course']['fullname']} — {w['section'].get('name', label)}"
        intro_text = "\n\n".join(intros)
        if not (files or intro_text):
            msg = ("დავალების ადგილი არსებობს, მაგრამ მასალა (ლექცია/ტექსტი) ჯერ არ არის ატვირთული.\n"
                   + "\n".join(l for l in lines if l.startswith("📌"))) if targets else "დავალება არ არის."
            return Overview(subject_key, week, title, msg, has_content=False)
        return Overview(subject_key, week, title, "\n".join(lines), files, intro_text, targets)

    drv = _drive()
    items = [f for f in drv.children(settings.drive_root_folder_id)
             if "დავალება" in f["name"] and week in numbers_in(f["name"])]
    if not items:
        return Overview(subject_key, week, f"დავალება {label}", "დავალება არ არის.", has_content=False)
    kids = drv.children(items[0]["id"])
    student = [k for k in kids if k["name"].strip() == settings.drive_student_folder]
    if not student:
        raise PipelineError(f"'{items[0]['name']}'-ში საქაღალდე '{settings.drive_student_folder}' ვერ ვიპოვე")
    src = [k for k in kids if k["id"] != student[0]["id"] and not k["mimeType"].endswith("folder")]
    files = [drv.download(k, work / "src") for k in src]
    lines = [f"📎 {f.name}" for f in files]
    target = {"kind": "drive", "folder_id": student[0]["id"], "label": "Drive"}
    return Overview(subject_key, week, items[0]["name"], "\n".join(lines) or "საქაღალდეში ფაილი არ არის.",
                    files, "", [target], bool(files))


# ---------------------------------------------------------------- generating
def _task_text(ov, chosen):
    parts = [ov.intro] if ov.intro else []
    for f in chosen:
        try:
            parts.append(extract_text(f))
        except ValueError:
            pass            # e.g. a lecture .pptx is not assignment text
    return "\n\n".join(p for p in parts if p and p.strip())


def _job(ov, skill, upload_file, extra, info, usage):
    only = ov.targets[0] if len(ov.targets) == 1 else {}      # several places -> the user picks later
    return Job(ov.subject, skill, ov.week, ov.label, upload_file, extra, only, info, list(ov.targets),
               usage.summary() if usage.calls else "💰 ხარჯი: $0 (cppwork მოდელს არ იყენებს)")


def estimate(ov, skill, chosen=None):
    """-> (rows, note). rows = [(model_key, name, usd)]: rough cost of running an LLM skill on each model,
    before running it. Haiku 5.5 first judges how big every task is; if that call fails a default
    "typical task" estimate is used."""
    text = _task_text(ov, list(ov.files if chosen is None else chosen))
    sizes = run_judge(text)
    rows = [(k, m["name"], pricing.estimate_cost(skill, text, k, sizes)) for k, m in pricing.MODELS.items()]
    note = (f"გამოთვლა: Haiku 5.5-მა დავალებები შეაფასა ({len(sizes)} ამოცანა: "
            f"{sizes.count('S')} მცირე, {sizes.count('M')} საშუალო, {sizes.count('L')} დიდი)"
            if sizes else "გამოთვლა სტანდარტული ამოცანის ზომით (Haiku-ს შეფასება ვერ მოხერხდა)")
    return rows, note


def run_judge(text):
    from .runners import judge_task_sizes
    return judge_task_sizes(text)


def prepare(ov, skill, chosen=None, model=None):
    """Run `skill` on the chosen source files (default: all files of the week).
    `model` = a key of pricing.MODELS (LLM skills only)."""
    _require_profile()
    usage = pricing.start_tracking()
    model_id = pricing.MODELS[model]["id"] if model else None
    chosen = list(ov.files if chosen is None else chosen)
    course = SUBJECTS[ov.subject]["title"]
    work = new_workdir()
    info = ov.title

    if skill == "cppwork":
        pptx = next((f for f in chosen if Path(f).suffix.lower() == ".pptx"), None)
        if pptx is None:
            raise PipelineError("cppwork-ს სჭირდება ლექციის .pptx ფაილი — აირჩიე ის")
        docx, log = run_cppwork(pptx, ov.label, work, course)
        return _job(ov, skill, docx, [], info + "\n" + log[-600:], usage)

    text = _task_text(ov, chosen)
    if len(text.strip()) < 20:
        raise PipelineError("დავალების ტექსტი ვერ ამოვიღე არჩეული ფაილიდან — სცადე სხვა ფაილი")
    if skill == "latexwork":
        pdf, zipped, _ = run_latexwork(text, ov.label, work, course, model_id)
        return _job(ov, skill, pdf, [zipped], info, usage)
    if skill == "jupiterwork":
        nb, extra, _ = run_jupiterwork(text, ov.label, work, course, model_id)
        return _job(ov, skill, nb, extra, info, usage)
    raise PipelineError(f"უცნობი skill: {skill}")


# ---------------------------------------------------------------- uploading
def submit(job):
    t = job.target
    if t.get("kind") == "moodle":
        _moodle().submit_file(t["assignment_id"], job.upload_file, finalize=settings.moodle_finalize)
        return "✅ ატვირთულია elearning-ზე" + (" და გაგზავნილია" if settings.moodle_finalize else " (შენახულია)")
    if t.get("kind") == "drive":
        _drive().upload(t["folder_id"], job.upload_file, job.upload_file.name)
        return f"✅ ატვირთულია Drive-ზე ({settings.drive_student_folder})"
    raise PipelineError("ატვირთვის ადგილი ვერ ვიპოვე (ამ კვირაში დავალების მოდული არ არის)")
