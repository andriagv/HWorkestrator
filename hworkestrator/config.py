"""Settings from environment variables (.env for local development)."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional in production
    pass


def _bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # optional reverse proxy for api.telegram.org (some hosts, e.g. Hugging Face Spaces, block Telegram);
    # e.g. https://tg-proxy.<you>.workers.dev  — see deploy/cloudflare_telegram_proxy.js
    telegram_api_base: str = os.getenv("TELEGRAM_API_BASE", "").rstrip("/")
    owner_id: int = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)

    moodle_url: str = os.getenv("MOODLE_URL", "https://elearning.gtu.ge").rstrip("/")
    moodle_token: str = os.getenv("MOODLE_TOKEN", "")
    # also press "Submit assignment" after saving (only if the course uses draft submissions)
    moodle_finalize: bool = _bool("MOODLE_FINALIZE", False)

    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    # ANTHROPIC_API_KEY (and optional ANTHROPIC_BASE_URL) are read by the anthropic SDK itself

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_refresh_token: str = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    drive_root_folder_id: str = os.getenv("DRIVE_ROOT_FOLDER_ID", "")
    # name of your subfolder inside each "დავალება N" folder; usually equals the group number
    drive_student_folder: str = os.getenv("DRIVE_STUDENT_FOLDER") or os.getenv("STUDENT_GROUP", "")

    # personal data lives only in .env (never in the code / git)
    student_name: str = os.getenv("STUDENT_NAME", "")
    student_group: str = os.getenv("STUDENT_GROUP", "")

    mode: str = os.getenv("BOT_MODE", "polling")          # polling | webhook
    webhook_url: str = os.getenv("WEBHOOK_URL", "")        # https://<host>
    port: int = int(os.getenv("PORT", "8080"))
    health_port: int = int(os.getenv("HEALTH_PORT", "0") or 0)    # >0 -> serve a tiny "alive" page there
    workdir: str = os.getenv("WORKDIR", "/tmp/hworkestrator")


settings = Settings()
