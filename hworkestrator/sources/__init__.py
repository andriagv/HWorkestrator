"""Sources: where assignments come from and where the finished work goes. One module per platform.

Every source module provides the same functions (the pipeline calls only these):
    list_items(subject_key)              -> [(button label, key)]   what the user can pick (weeks, files...)
    overview(subject_key, key, workdir)  -> models.Overview         downloaded files, assignment text, upload targets
    submit(target, path)                 -> str                     upload `path` to one of the overview's targets
A subject in registry.SUBJECTS names its source ("source": "moodle"); every upload target carries
{"kind": <source name>}. To add a platform (another LMS...): write a module with these three functions and
add it to SOURCES below.
"""
from importlib import import_module

SOURCES = {           # source name used in registry.SUBJECTS -> module in this package
    "moodle": "moodle",
    "drive": "gdrive",
}


def get(name):
    if name not in SOURCES:
        raise KeyError(f"unknown source '{name}' — known: {', '.join(SOURCES)}")
    return import_module(f"{__name__}.{SOURCES[name]}")
