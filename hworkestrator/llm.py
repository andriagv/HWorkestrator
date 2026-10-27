"""Calling Claude: one helper for every skill, plus the cheap task-size judge used for price estimates."""
import json
import re

from . import pricing
from .config import settings


def claude(system, user, max_tokens=12000, model=None):
    """One Claude call (streamed, so long outputs are allowed). Refuses a truncated answer."""
    import anthropic
    model = model or settings.anthropic_model
    with anthropic.Anthropic().messages.stream(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}]) as stream:
        msg = stream.get_final_message()
    pricing.record(model, msg.usage)                       # for the cost report
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("Claude-ის პასუხი ძალიან გრძელი გამოვიდა და შეწყდა (max_tokens)")
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def strip_fences(text):
    return re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())


def parse_json(raw):
    """The JSON object in a model answer (tolerates fences and text around it)."""
    raw = strip_fences(raw)
    return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])


SIZE_SYSTEM = r"""You help estimate the workload of a university assignment before it is solved.
Return ONLY JSON: {"tasks": [{"n": 1, "size": "S"}, ...]} — one entry per numbered task/problem.
size: "S" = trivial or one short answer, "M" = typical (some code or calculation + a paragraph),
"L" = heavy (model training, several plots/steps, long multi-part questions). No commentary."""


def judge_task_sizes(task_text):
    """Ask Haiku 5.5 (a fraction of a cent) how big each task is -> ["S"/"M"/"L", ...]. [] on failure."""
    try:
        raw = strip_fences(claude(SIZE_SYSTEM, task_text[:20000], 1000, pricing.MODELS["haiku"]["id"]))
        sizes = [t.get("size", "M") for t in json.loads(raw)["tasks"]]
        return [z if z in ("S", "M", "L") else "M" for z in sizes]
    except Exception:
        return []
