"""Send alerts to a Telegram chat through a bot."""


class TelegramError(Exception):
    pass


async def send(client, token: str, chat_id: str, text: str):
    resp = await client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
    )
    if resp.status_code != 200:
        # Never surface the request URL: it contains the bot token.
        try:
            detail = resp.json().get("description", "")
        except ValueError:
            detail = ""
        raise TelegramError(f"HTTP {resp.status_code} {detail}".strip())
