"""Prices, real-usage tracking, the Haiku task-size judge and the size-aware estimates."""
import pytest

from hworkestrator import llm, pricing
from hworkestrator.documents import n_tasks


def test_pricing_per_model_and_haiku_long_tier():
    # 1M input + 1M output tokens at list prices
    assert pricing.call_cost("claude-sonnet-5-5", 1_000_000, 1_000_000) == pytest.approx(2 + 10)
    assert pricing.call_cost("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(4 + 20)
    assert pricing.call_cost("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.5 + 2.5)   # >100k tier
    assert pricing.call_cost("claude-haiku-5-5", 100_000, 0) == pytest.approx(0.01)                 # <=100k tier
    assert pricing.call_cost("unknown-model", 10, 10) == 0.0


def test_usage_tracking_and_estimate_order():
    u = pricing.start_tracking()
    pricing.record("claude-sonnet-5-5", type("U", (), {"input_tokens": 1000, "output_tokens": 500})())
    assert (u.input_tokens, u.output_tokens) == (1000, 500)
    assert u.cost == pytest.approx((1000 * 2 + 500 * 10) / 1e6)
    assert "$" in u.summary()
    text = "დავალება 1. ა\\nდავალება 2. ბ\\n" * 3
    for skill in ("jupiterwork", "latexwork", "secwork"):
        c = {k: pricing.estimate_cost(skill, text, k) for k in pricing.MODELS}
        assert c["haiku"] < c["sonnet"] < c["opus"] < c["fable"]
    assert pricing.estimate_cost("cppwork", text, "opus") == 0 and not pricing.uses_llm("cppwork")


def test_size_judging_and_size_aware_estimate(monkeypatch):
    monkeypatch.setattr(llm, "claude", lambda *a, **k: '```json\n{"tasks":[{"n":1,"size":"S"},{"n":2,"size":"L"},{"n":3,"size":"x"}]}\n```')
    assert llm.judge_task_sizes("whatever") == ["S", "L", "M"]          # unknown size -> M
    monkeypatch.setattr(llm, "claude", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert llm.judge_task_sizes("whatever") == []                       # failure -> caller falls back
    small = pricing.estimate_cost("jupiterwork", "x" * 400, "sonnet", ["S", "S"])
    big = pricing.estimate_cost("jupiterwork", "x" * 400, "sonnet", ["L", "L"])
    assert small < big


def test_task_count():
    assert n_tasks("Task 1: a\nTask 2: b\nამოცანა 3. გ\nProblem 4) d") == 4
    assert n_tasks("no numbered tasks") == 1
