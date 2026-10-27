"""Model menu, prices and cost estimates for the LLM skills.

Prices: USD per million tokens, from Anthropic's pricing page
https://platform.claude.com/docs/en/about-claude/pricing  (checked 2026-10-22; update here if they change).
"""
import contextvars
import re
from dataclasses import dataclass, field

# key -> model; Haiku 5.5 has a pricier tier for prompts over 100k tokens
MODELS = {
    "haiku":  {"id": "claude-haiku-5-5",  "name": "Haiku 5.5",  "in": 0.10, "out": 0.50,
               "long_in": 0.50, "long_out": 2.50, "long_over": 100_000, "emoji": "⚡"},
    "sonnet": {"id": "claude-sonnet-5-5", "name": "Sonnet 5.5", "in": 2.0, "out": 10.0, "emoji": "⚖️"},
    "opus":   {"id": "claude-opus-5-5",   "name": "Opus 5.5",   "in": 4.0, "out": 20.0, "emoji": "🧠"},
    "fable":  {"id": "claude-fable-5-1",  "name": "Fable 5.1",  "in": 10.0, "out": 50.0, "emoji": "🏆"},
}
LLM_SKILLS = ("latexwork", "jupiterwork", "secwork")           # cppwork never calls a model


def by_id(model_id):
    return next((m for m in MODELS.values() if m["id"] == model_id), None)


def call_cost(model_id, in_tok, out_tok):
    """USD for one API call."""
    m = by_id(model_id)
    if m is None:
        return 0.0
    long = in_tok > m.get("long_over", float("inf"))
    pin = m["long_in"] if long else m["in"]
    pout = m["long_out"] if long else m["out"]
    return (in_tok * pin + out_tok * pout) / 1_000_000


def fmt_usd(x):
    if x < 0.001:
        return "<$0.001"
    return f"${x:.3f}" if x < 0.1 else f"${x:.2f}"


# ---------------------------------------------------------------- measuring real usage
@dataclass
class Usage:
    calls: list = field(default_factory=list)       # (model_id, input_tokens, output_tokens)

    def add(self, model_id, in_tok, out_tok):
        self.calls.append((model_id, in_tok, out_tok))

    @property
    def input_tokens(self):
        return sum(c[1] for c in self.calls)

    @property
    def output_tokens(self):
        return sum(c[2] for c in self.calls)

    @property
    def cost(self):
        return sum(call_cost(*c) for c in self.calls)

    def summary(self):
        if not self.calls:
            return "💰 ხარჯი: $0 (მოდელი არ გამოყენებულა)"
        name = (by_id(self.calls[0][0]) or {}).get("name", self.calls[0][0])
        return (f"💰 ფაქტობრივი ხარჯი: {fmt_usd(self.cost)} ({name}, {len(self.calls)} გამოძახება, "
                f"{self.input_tokens:,} შემავალი + {self.output_tokens:,} გამომავალი ტოკენი)")


_current = contextvars.ContextVar("hw_usage", default=None)


def start_tracking():
    u = Usage()
    _current.set(u)
    return u


def record(model_id, usage):
    u = _current.get()
    if u is not None and usage is not None:
        u.add(model_id, usage.input_tokens, usage.output_tokens)


# ---------------------------------------------------------------- estimates before running
TASK_WORDS = r"(?:დავალება|ამოცანა|პრობლემა|Task|Problem|Exercise|Question)"


def n_tasks(task_text):
    found = {int(n) for n in re.findall(TASK_WORDS + r"\s*(\d+)\s*[.:)]", task_text, flags=re.I)}
    return max(len(found), 1)


# output tokens per task by size (S small / M typical / L heavy); measured: a typical jupiterwork task is
# ~1.25k tokens of code and ~1k tokens of explanation, a typical latexwork task ~3.5k tokens
SIZE_TOKENS = {
    "latexwork":   {"S": 1500, "M": 3500, "L": 6000},
    "jupiterwork": {"S": 700,  "M": 1250, "L": 2000},        # code pass
    "secwork":     {"S": 600,  "M": 1200, "L": 2200},        # statement + code pass (JSON)
}
EXPLAIN_TOKENS = {"S": 500, "M": 1000, "L": 1600}              # jupiterwork explanation pass


def estimate_tokens(skill, task_text, sizes=None):
    """Rough list of (input_tokens, output_tokens), one per API call. `sizes` = list of "S"/"M"/"L"
    per task (judged by Haiku); without it every task counts as "M". Georgian text is token-hungry,
    so ~2 characters per token is assumed. Real usage is shown after the run."""
    sizes = list(sizes) if sizes else ["M"] * n_tasks(task_text)
    task_in = len(task_text) // 2
    if skill == "latexwork":
        return [(task_in + 900, sum(SIZE_TOKENS["latexwork"][z] for z in sizes) + 500)]
    if skill == "jupiterwork":
        # +15% margin: an execution error now and then triggers an extra repair call
        first_out = int((sum(SIZE_TOKENS["jupiterwork"][z] for z in sizes) + 300) * 1.15)
        second_out = int((sum(EXPLAIN_TOKENS[z] for z in sizes) + 200) * 1.15)
        return [(task_in + 1400, first_out),                      # write the notebook (code)
                (task_in + first_out + 500, second_out)]          # explanations from real outputs
    if skill == "secwork":
        first_out = int((sum(SIZE_TOKENS["secwork"][z] for z in sizes) + 300) * 1.15)
        second_out = int((sum(EXPLAIN_TOKENS[z] for z in sizes) + 600) * 1.15)   # + conclusions
        return [(task_in + 900, first_out),                       # tasks + code
                (task_in + first_out + 600, second_out)]          # explanations from real outputs
    return []


def estimate_cost(skill, task_text, model_key, sizes=None):
    m = MODELS[model_key]
    return sum(call_cost(m["id"], i, o) for i, o in estimate_tokens(skill, task_text, sizes))
