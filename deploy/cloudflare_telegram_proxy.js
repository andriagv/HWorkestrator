// Cloudflare Worker: forwards Telegram Bot API calls (for hosts that block api.telegram.org).
// Deploy: Cloudflare dashboard -> Workers & Pages -> Create -> "Hello World" -> paste this -> Deploy.
// Then set TELEGRAM_API_BASE=https://<worker-name>.<your-subdomain>.workers.dev in the bot's environment.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/bot") && !url.pathname.startsWith("/file/bot")) {
      return new Response("HWorkestrator Telegram proxy\n", { status: 200 });
    }
    url.protocol = "https:";
    url.hostname = "api.telegram.org";
    url.port = "";
    return fetch(new Request(url.toString(), request));
  },
};
