"""The four steps the bot walks through, independent of platform and skill:

    list_items(subject)   -> what to pick (weeks, files)      — asks the subject's source
    overview(subject,key) -> look at it (files, text, targets) — asks the subject's source
    prepare(ov, skill)    -> run the skill, get a Job          — asks skills/<skill>/runner.py
    submit(job)           -> upload to the chosen target       — asks the target's source
"""
import tempfile
from pathlib import Path

from . import llm, pricing, skills, sources
from .config import settings
from .documents import extract_text
from .models import Job, Overview, PipelineError  # noqa: F401 (Overview, PipelineError: used by callers)
from .registry import SUBJECTS


def new_workdir():
    Path(settings.workdir).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=settings.workdir))


def _source(subject_key):
    return sources.get(SUBJECTS[subject_key]["source"])


# ---------------------------------------------------------------- looking
def list_items(subject_key):
    """[(button label, key)]: Moodle weeks, or the assignment files of the Drive folder (newest first)."""
    return _source(subject_key).list_items(subject_key)


def overview(subject_key, key):
    """Describe a week / assignment (files, text, what is already uploaded) without generating."""
    return _source(subject_key).overview(subject_key, key, new_workdir())


def drive_folder(folder_id=None):
    """A Drive folder for the upload picker (see sources.gdrive.folder)."""
    return sources.get("drive").folder(folder_id)


# ---------------------------------------------------------------- generating
def _task_text(ov, chosen):
    parts = [ov.intro] if ov.intro else []
    for f in chosen:
        try:
            parts.append(extract_text(f))
        except ValueError:
            pass            # e.g. a lecture .pptx is not assignment text
    return "\n\n".join(p for p in parts if p and p.strip())


def estimate(ov, skill, chosen=None):
    """-> (rows, note). rows = [(model_key, name, usd)]: rough cost of running an LLM skill on each model,
    before running it. Haiku 5.5 first judges how big every task is; if that call fails a default
    "typical task" estimate is used."""
    text = _task_text(ov, list(ov.files if chosen is None else chosen))
    sizes = llm.judge_task_sizes(text)
    rows = [(k, m["name"], pricing.estimate_cost(skill, text, k, sizes)) for k, m in pricing.MODELS.items()]
    note = (f"გამოთვლა: Haiku 5.5-მა დავალებები შეაფასა ({len(sizes)} ამოცანა: "
            f"{sizes.count('S')} მცირე, {sizes.count('M')} საშუალო, {sizes.count('L')} დიდი)"
            if sizes else "გამოთვლა სტანდარტული ამოცანის ზომით (Haiku-ს შეფასება ვერ მოხერხდა)")
    return rows, note


def prepare(ov, skill, chosen=None, model=None):
    """Run `skill` on the chosen source files (default: all files of the week / assignment).
    `model` = a key of pricing.MODELS (LLM skills only)."""
    if not (settings.student_name and settings.student_group):
        raise PipelineError("STUDENT_NAME და STUDENT_GROUP უნდა იყოს მითითებული .env-ში")
    try:
        runner = skills.load(skill)
    except ModuleNotFoundError:
        raise PipelineError(f"უცნობი skill: {skill}") from None
    usage = pricing.start_tracking()
    chosen = list(ov.files if chosen is None else chosen)
    if runner.NEEDS == "lecture":
        types = runner.LECTURE_TYPES
        found = sorted((f for f in chosen if Path(f).suffix.lower() in types),
                       key=lambda f: types.index(Path(f).suffix.lower()))
        if not found:
            raise PipelineError(f"{skill}-ს სჭირდება ლექციის ფაილი ({', '.join(types)}) — აირჩიე ის")
        source = found[0]
    else:
        source = _task_text(ov, chosen)
        if len(source.strip()) < 20:
            raise PipelineError("დავალების ტექსტი ვერ ამოვიღე არჩეული ფაილიდან — სცადე სხვა ფაილი")
    model_id = pricing.MODELS[model]["id"] if model and runner.USES_LLM else None
    upload, extra, log = runner.run(source, ov.label, new_workdir(), SUBJECTS[ov.subject]["title"], model_id)
    info = ov.title if runner.USES_LLM else ov.title + "\n" + log[-600:]
    only = ov.targets[0] if len(ov.targets) == 1 else {}      # several places -> the user picks later
    return Job(ov.subject, skill, ov.week, ov.label, upload, list(extra), only, info, list(ov.targets),
               usage.summary() if usage.calls else "💰 ხარჯი: $0 (ამ skill-ს მოდელი არ სჭირდება)")


# ---------------------------------------------------------------- uploading
def submit(job):
    t = job.target
    if not t.get("kind"):
        raise PipelineError("ატვირთვის ადგილი ვერ ვიპოვე (ამ კვირაში დავალების მოდული არ არის)")
    return sources.get(t["kind"]).submit(t, job.upload_file)
