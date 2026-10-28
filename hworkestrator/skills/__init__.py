"""Skills: turn one assignment into the finished file. One folder per skill:

    <skill>/runner.py   what the bot calls: run() and the Claude prompts
    <skill>/scripts/    standalone build scripts (layout, compiling, executing) — usable without the bot
    <skill>/assets/     templates and logos

Every runner.py provides:
    NEEDS = "text" | "lecture"  what run() gets: the assignment text, or a lecture file
                                (then also LECTURE_TYPES = (".pptx", ".pdf", ".docx"), preferred first)
    USES_LLM = True | False     False -> no model choice and no cost
    run(source, label, outdir, course, model=None) -> (upload_file, extra_files, log)
        label  = assignment/week number for the header and file name; course = subject title
    estimate(task_in_tokens, sizes) -> [(input_tokens, output_tokens), ...]   one per Claude call (USES_LLM only)
Shared helpers live in common.py; the button label of a skill is in registry.SKILLS.
To add a skill: copy the closest folder, change it, add it to registry.SKILLS.
"""
from importlib import import_module


def load(name):
    """The runner module of a skill."""
    return import_module(f"{__name__}.{name}.runner")
