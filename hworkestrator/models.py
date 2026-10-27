"""The data passed between sources, the pipeline, the skills and the bot."""
from dataclasses import dataclass, field
from pathlib import Path

from .sources.weeks import int_to_roman


class PipelineError(RuntimeError):
    """A problem to show to the user in the chat (missing setting, wrong file...)."""


@dataclass
class Overview:
    """One week (Moodle) or one assignment file (Drive), as a source sees it, before anything is generated."""
    subject: str
    week: int
    title: str
    text: str                                         # what to show in the chat
    files: list = field(default_factory=list)         # local source files (lecture, attachments...)
    intro: str = ""                                   # assignment text written on the page
    targets: list = field(default_factory=list)       # upload places: {"kind": <source>, ...}
    has_content: bool = True                          # False -> "no assignment"
    number: str = ""                                  # Drive: the assignment number from the file name

    @property
    def label(self):
        # Moodle weeks are roman ("VI კვირა"); Drive assignments keep their own number ("დავალება 3")
        return self.number or int_to_roman(self.week)


@dataclass
class Job:
    """A generated result waiting for the user's ✅ and an upload target."""
    subject: str
    skill: str
    week: int
    label: str
    upload_file: Path                                 # what gets uploaded
    extra_files: list = field(default_factory=list)   # also sent to Telegram (e.g. tex zip, editable docx)
    target: dict = field(default_factory=dict)        # chosen upload place
    info: str = ""
    targets: list = field(default_factory=list)       # all possible upload places
    cost_note: str = ""                               # real token usage / cost of the run
