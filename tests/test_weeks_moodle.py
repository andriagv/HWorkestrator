import shutil
from pathlib import Path

import pytest

from hworkestrator import pipeline
from hworkestrator.moodle import Moodle, module_files
from hworkestrator.weeks import find_week_section, int_to_roman, numbers_in, parse_week

LECTURE = Path.home() / "Downloads" / "Lecture IV_struct.pptx"


def test_parse_week():
    assert [parse_week(x) for x in ("VI", "6", "კვირა 6", "iv", "Week 12")] == [6, 6, 6, 4, 12]
    assert parse_week("abc") is None
    assert int_to_roman(14) == "XIV"


def test_numbers_in():
    assert 6 in numbers_in("VI კვირა") and 10 in numbers_in("კვირა 10")


SECTIONS = [
    {"name": "General", "section": 0, "modules": []},
    {"name": "IV კვირა", "section": 4, "modules": [
        {"id": 111, "modname": "resource", "name": "Lecture IV",
         "contents": [{"type": "file", "filename": "Lecture IV_struct.pptx",
                       "fileurl": "https://x/pluginfile.php/1/a.pptx"}]},
        {"id": 222, "modname": "assign", "name": "დავალება 4"}]},
    {"name": "V კვირა", "section": 5, "modules": []},
]


def test_find_week_section_and_modules():
    s = find_week_section(SECTIONS, 4)
    assert s["name"] == "IV კვირა"
    assert module_files(s["modules"][0]) == [("https://x/pluginfile.php/1/a.pptx", "Lecture IV_struct.pptx")]
    assert find_week_section(SECTIONS, 9) is None


class FakeMoodle(Moodle):
    def __init__(self):
        super().__init__("https://x", "T")
        self.submitted = None

    def call(self, fn, **p):
        return {
            "core_webservice_get_site_info": {"userid": 7},
            "core_enrol_get_users_courses": [{"id": 5, "fullname": "მონაცემთა სტრუქტურები და ალგორითმები",
                                              "shortname": "DSA"}],
            "core_course_get_contents": SECTIONS,
            "mod_assign_get_submission_status": {"lastattempt": {"submission": {"plugins": [
                {"fileareas": [{"files": [{"filename": "old.docx"}]}]}]}}},
            "mod_assign_get_assignments": {"courses": [{"assignments": [
                {"id": 999, "cmid": 222, "intro": "<p>x</p>"}]}]},
        }[fn]

    def download(self, url, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(LECTURE, dest)
        return Path(dest)

    def submit_file(self, assignment_id, path, finalize=False):
        self.submitted = (assignment_id, Path(path).name)


def test_week_lookup():
    w = FakeMoodle().week("სტრუქტურები და ალგორითმები", 4)
    assert [m["id"] for m in w["resources"]] == [111]
    assert [(i["module"]["id"], i["assignment"]["id"]) for i in w["assigns"]] == [(222, 999)]


@pytest.mark.skipif(not LECTURE.exists(), reason="sample lecture not available")
def test_cppwork_moodle_end_to_end(monkeypatch, tmp_path):
    fake = FakeMoodle()
    monkeypatch.setattr(pipeline, "_moodle", lambda: fake)
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    ov = pipeline.overview("dsa", 4)
    assert [f.name for f in ov.files] == ["Lecture IV_struct.pptx"]
    job = pipeline.prepare(ov, "cppwork")
    assert job.upload_file.suffix == ".docx" and job.upload_file.exists()
    assert job.target == {"kind": "moodle", "assignment_id": 999, "label": "დავალება 4", "existing": ["old.docx"]}
    assert job.targets == [job.target]
    monkeypatch.setattr(pipeline.settings.__class__, "moodle_finalize", False, raising=False)
    pipeline.submit(job)
    assert fake.submitted == (999, "დავალება IV - Test Student.docx")


def test_cppwork_needs_a_pptx_among_chosen_files(tmp_path):
    ov = pipeline.Overview("dsa", 4, "t", "x", files=[tmp_path / "task.pdf"], intro="y" * 30,
                           targets=[{"kind": "moodle", "assignment_id": 1}])
    with pytest.raises(pipeline.PipelineError):
        pipeline.prepare(ov, "cppwork", chosen=[tmp_path / "task.pdf"])


def test_unknown_skill_is_rejected(tmp_path):
    ov = pipeline.Overview("dsa", 4, "t", "x", files=[], intro="y" * 30)
    with pytest.raises(pipeline.PipelineError):
        pipeline.prepare(ov, "nope")


def test_task_completeness_check():
    from hworkestrator import runners
    text = "დავალება 1. ა\nდავალება 2. ბ\nდავალება 3: გ"
    assert runners.expected_tasks(text) == [1, 2, 3]
    cells = "# %% [markdown]\n# ## დავალება 1. ა\n# %% [markdown]\n# ## დავალება 3. გ\n"
    assert runners.missing_tasks(cells, text) == [2]


def test_week_with_several_assignments_lists_them_all(monkeypatch, tmp_path):
    """"დავალება" + "პრაქტიკული 4" + lecture: every activity is inspected, user later picks the target."""
    sections = [{"name": "IV კვირა", "section": 4, "modules": [
        {"id": 1, "modname": "assign", "name": "დავალება"},
        {"id": 2, "modname": "resource", "name": "ლექცია 4", "contents": [
            {"type": "file", "filename": "lec.docx", "fileurl": "https://x/pluginfile.php/a/lec.docx"}]},
        {"id": 3, "modname": "assign", "name": "პრაქტიკული 4"},
        {"id": 4, "modname": "folder", "name": "მასალა", "contents": [
            {"type": "file", "filename": "data.pdf", "fileurl": "https://x/pluginfile.php/a/data.pdf"}]},
        {"id": 5, "modname": "resource", "name": "hidden", "uservisible": False}]}]

    class Many(FakeMoodle):
        def call(self, fn, **p):
            if fn == "core_course_get_contents":
                return sections
            if fn == "mod_assign_get_assignments":
                return {"courses": [{"assignments": [
                    {"id": 10, "cmid": 1, "intro": ""},
                    {"id": 11, "cmid": 3, "intro": "<p>Practice task text</p>"}]}]}
            return super().call(fn, **p)

        def download(self, url, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("x")
            return Path(dest)

    fake = Many()
    monkeypatch.setattr(pipeline, "_moodle", lambda: fake)
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    ov = pipeline.overview("dsa", 4)
    assert sorted(f.name for f in ov.files) == ["data.pdf", "lec.docx"]       # hidden module skipped
    assert [t["label"] for t in ov.targets] == ["დავალება", "პრაქტიკული 4"]
    assert "Practice task text" in ov.intro and "პრაქტიკული 4" in ov.text


def test_pricing_per_model_and_haiku_long_tier():
    from hworkestrator import pricing
    # 1M input + 1M output tokens at list prices
    assert pricing.call_cost("claude-sonnet-5-5", 1_000_000, 1_000_000) == pytest.approx(2 + 10)
    assert pricing.call_cost("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(4 + 20)
    assert pricing.call_cost("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.5 + 2.5)   # >100k tier
    assert pricing.call_cost("claude-haiku-5-5", 100_000, 0) == pytest.approx(0.01)                 # <=100k tier
    assert pricing.call_cost("unknown-model", 10, 10) == 0.0


def test_usage_tracking_and_estimate_order():
    from hworkestrator import pricing
    u = pricing.start_tracking()
    pricing.record("claude-sonnet-5-5", type("U", (), {"input_tokens": 1000, "output_tokens": 500})())
    assert (u.input_tokens, u.output_tokens) == (1000, 500)
    assert u.cost == pytest.approx((1000 * 2 + 500 * 10) / 1e6)
    assert "$" in u.summary()
    text = "დავალება 1. ა\\nდავალება 2. ბ\\n" * 3
    c = {k: pricing.estimate_cost("jupiterwork", text, k) for k in pricing.MODELS}
    assert c["haiku"] < c["sonnet"] < c["opus"] < c["fable"]
    assert pricing.estimate_cost("cppwork", text, "opus") == 0


def test_splice_answers_replaces_only_the_answer_blocks():
    from hworkestrator import runners
    src = ("# %% [markdown]\n# ## დავალება 1. ა\n# %%\nprint(1)\n# %% [markdown]\n# ### პასუხი\n# old1\n"
           "# %% [markdown]\n# ## დავალება 2. ბ\n# %%\nprint(2)\n# %% [markdown]\n# ### პასუხი\n# old2\n# more\n")
    out = runners.splice_answers(src, {1: "new **one**", 2: "line a\n\nline b"})
    assert "old1" not in out and "old2" not in out and "more" not in out
    assert "# new **one**" in out and "# line a\n#\n# line b" in out
    assert out.count("print(") == 2 and "## დავალება 2" in out
    with pytest.raises(ValueError):
        runners.splice_answers(src, {7: "x"})


def test_size_judging_and_size_aware_estimate(monkeypatch):
    from hworkestrator import pricing, runners
    monkeypatch.setattr(runners, "_claude", lambda *a, **k: '```json\n{"tasks":[{"n":1,"size":"S"},{"n":2,"size":"L"},{"n":3,"size":"x"}]}\n```')
    assert runners.judge_task_sizes("whatever") == ["S", "L", "M"]          # unknown size -> M
    monkeypatch.setattr(runners, "_claude", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert runners.judge_task_sizes("whatever") == []                       # failure -> caller falls back
    small = pricing.estimate_cost("jupiterwork", "x" * 400, "sonnet", ["S", "S"])
    big = pricing.estimate_cost("jupiterwork", "x" * 400, "sonnet", ["L", "L"])
    assert small < big


def test_english_and_georgian_task_labels_are_counted():
    from hworkestrator import pricing, runners
    text = "Task 1: a\nTask 2: b\nამოცანა 3. გ\nProblem 4) d"
    assert pricing.n_tasks(text) == 4 and runners.expected_tasks(text) == [1, 2, 3, 4]
    cells = "# %% [markdown]\n# ## Task 1: a\n# %% [markdown]\n# ## Task 2: b\n"
    assert runners.missing_tasks(cells, text) == [3, 4]


def test_telegram_api_base_is_used_when_set(monkeypatch):
    from hworkestrator import bot, config
    monkeypatch.setattr(bot, "settings", config.Settings(telegram_token="1:a", owner_id=1,
                                                         telegram_api_base="https://tg.example.workers.dev"))
    app = bot.build_app()
    assert app.bot.base_url == "https://tg.example.workers.dev/bot1:a"
