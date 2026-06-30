import os
import html as html_module
import re
from dotenv import load_dotenv
import httpx
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

ADMIN_NUMBERS = set(
    n.strip().lstrip("+")
    for n in os.getenv("ADMIN_NUMBERS", "").split(",")
    if n.strip()
)

# user_id -> {"role": "admin" | "guest"}
user_sessions: dict = {}


# ---------------------------------------------------------------------------
# Markdown → Telegram HTML formatter
# ---------------------------------------------------------------------------

def _format_for_telegram(text: str) -> str:
    placeholders: dict[str, str] = {}
    idx = [0]

    def _key(prefix: str) -> str:
        k = f"\x00{prefix}{idx[0]}\x00"
        idx[0] += 1
        return k

    def _replace_code_block(m: re.Match) -> str:
        key = _key("CODE")
        content = html_module.escape(m.group(1).rstrip())
        placeholders[key] = f"<pre><code>{content}</code></pre>"
        return key

    text = re.sub(r"```(?:\w+)?\n?([\s\S]*?)```", _replace_code_block, text)
    text = html_module.escape(text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*\n]+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", text)

    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def _send_chunks(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Share my phone number", request_contact=True)]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "Welcome! Please share your phone number to verify your access level.",
        reply_markup=keyboard,
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number.lstrip("+")
    user_id = update.effective_user.id
    is_admin = phone in ADMIN_NUMBERS
    role = "admin" if is_admin else "guest"

    user_sessions[user_id] = {"role": role}

    access_msg = (
        "You have <b>full access</b> including database queries and policy documents."
        if is_admin
        else "You have access to <b>company policy documents</b> only."
    )
    await update.message.reply_text(
        f"Verified! You are logged in as <b>{role.capitalize()}</b>.\n{access_msg}",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_sessions:
        await update.message.reply_text(
            "Please use /start to verify your phone number first."
        )
        return

    role = user_sessions[user_id]["role"]
    user_text = update.message.text

    await update.message.chat.send_action("typing")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{FASTAPI_URL}/chat",
                json={"message": user_text, "role": role},
            )
            response.raise_for_status()
            reply = response.json()["reply"]
    except httpx.ConnectError:
        await update.message.reply_text(
            "Cannot reach the server. Please make sure the API is running."
        )
        return
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"Server error: {e.response.status_code}")
        return

    formatted = _format_for_telegram(reply)
    for chunk in _send_chunks(formatted):
        await update.message.reply_text(chunk, parse_mode="HTML")


# ---------------------------------------------------------------------------

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"Bot is running. Calling API at {FASTAPI_URL}")
    app.run_polling()


if __name__ == "__main__":
    main()
