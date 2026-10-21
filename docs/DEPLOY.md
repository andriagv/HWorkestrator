# Running the bot in the cloud (so your computer can be off)

The bot is one Docker image (`Dockerfile`). Two free options:

## A) Oracle Cloud "Always Free" VM — always on (needs a bank card for sign-up, not charged)
1. Create an Always Free **Ampere A1** (ARM) VM, Ubuntu 22.04/24.04, with your SSH key.
2. On the VM:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io git
   git clone https://github.com/<you>/HWorkestrator.git && cd HWorkestrator
   nano .env            # paste the values from .env.example (BOT_MODE=polling)
   sudo docker build -t hworkestrator .
   sudo docker run -d --name hw --restart unless-stopped --env-file .env hworkestrator
   sudo docker logs -f hw
   ```
3. Update later: `git pull && sudo docker build -t hworkestrator . && sudo docker rm -f hw && sudo docker run -d --name hw --restart unless-stopped --env-file .env hworkestrator`.

## B) Hugging Face Space (Docker) — no card
1. huggingface.co → New Space → SDK **Docker** (blank), hardware **CPU basic (free)**, visibility **Public**
   (needed for the uptime pings; code is public on GitHub anyway, secrets stay hidden).
2. Space → **Settings → Variables and secrets** → add as **Secrets**: `TELEGRAM_BOT_TOKEN`, `OWNER_TELEGRAM_ID`,
   `MOODLE_TOKEN`, `ANTHROPIC_API_KEY`, `STUDENT_NAME`, `STUDENT_GROUP`, `DRIVE_ROOT_FOLDER_ID`,
   `DRIVE_STUDENT_FOLDER`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`
   (the last four only if you use Drive). Add as plain variable: `BOT_MODE=polling`.
3. Push the code (HF asks for your username + an access token with *write* permission as password):
   ```bash
   bash deploy/push_to_space.sh <hf-user>/<space-name>
   ```
4. The free Space **sleeps when nobody visits it**, which would stop the bot. Keep it awake: create a free
   [UptimeRobot](https://uptimerobot.com) HTTP monitor for `https://<hf-user>-<space-name>.hf.space` every 5 minutes
   (the bot serves a tiny "alive" page on port 7860 for this).

## Before switching on the cloud bot
Two bots with the same Telegram token fight each other (`Conflict` error): **stop the bot on your computer** first.

## Notes
- Nothing is stored on the server; generated files live in a temp folder.
- `ANTHROPIC_BASE_URL` must not be set in the cloud (it only exists in some local tools).
- Free-tier terms change; check the provider's page before relying on them.
