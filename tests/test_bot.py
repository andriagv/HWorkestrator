"""The Telegram app wiring."""
from hworkestrator import bot, config


def test_telegram_api_base_is_used_when_set(monkeypatch):
    monkeypatch.setattr(bot, "settings", config.Settings(telegram_token="1:a", owner_id=1,
                                                         telegram_api_base="https://tg.example.workers.dev"))
    app = bot.build_app()
    assert app.bot.base_url == "https://tg.example.workers.dev/bot1:a"


def test_every_callback_has_a_handler():
    patterns = [h.pattern.pattern for group in bot.build_app().handlers.values() for h in group
                if hasattr(h, "pattern") and h.pattern is not None]
    import re
    for data in ("subj:infosec", "home", "wk:4", "wk:1JYarX8PAVn-3eajvPwfr1g3U_y5q3S6Z", "src:all", "skill:secwork",
                 "mdl:haiku", "ok:0", "no", "dir:root", "put:14hbnJQse51PHn4Q70xtdNCJ5x0OXDmm7"):
        assert any(re.match(p, data) for p in patterns), data
