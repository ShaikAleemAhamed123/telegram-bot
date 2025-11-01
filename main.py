from fastapi import FastAPI, Request
import httpx
from pytubefix import YouTube
from pytubefix.exceptions import BotDetection
import asyncio
import re
import os

app = FastAPI()
BOT_TOKEN = "8311901559:AAEJIF3HbxtkVnf8YjVYQ5IBgAfcPl9Axh4"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

YT_URL_PATTERN = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"


@app.post("/hello")
async def webhook(request: Request):
    data = await request.json()
    print("Update received:", data)

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id:
        return {"ok": True}

    try:
        # if it's a YouTube link
        if re.match(YT_URL_PATTERN, text):
            await send_message(chat_id, "🎥 Downloading your video... Please wait.")

            try:
                yt = await asyncio.to_thread(YouTube, text)
                stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
                if not stream:
                    await send_message(chat_id, "❌ Couldn't find any downloadable video streams.")
                    return {"ok": True}

                file_path = await asyncio.to_thread(stream.download)
                if not file_path or not os.path.exists(file_path):
                    await send_message(chat_id, "❌ Download failed, file not found.")
                    return {"ok": True}

                # Check Telegram file size limit (~50 MB for bots)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if size_mb > 50:
                    await send_message(chat_id, f"⚠️ Video too large ({size_mb:.1f} MB). Telegram only allows up to 50 MB.")
                    os.remove(file_path)
                    return {"ok": True}

                async with httpx.AsyncClient() as client:
                    with open(file_path, "rb") as video_file:
                        files = {"video": video_file}
                        data_payload = {"chat_id": chat_id}
                        await client.post(f"{TELEGRAM_API}/sendVideo", data=data_payload, files=files)

                os.remove(file_path)
                await send_message(chat_id, "✅ Video sent successfully!")
                return {"ok": True}

            except BotDetection:
                await send_message(chat_id, "🚫 YouTube blocked this request as automated. Try again later.")
            except Exception as e:
                await send_message(chat_id, f"⚠️ Download failed: {e}")

        else:
            await send_message(chat_id, f"You said: {text}")

    except Exception as e:
        # catch-all to avoid infinite loop
        print("Webhook error:", e)
        await send_message(chat_id, f"⚠️ An error occurred: {e}")

    # Always return ok so Telegram stops retrying
    return {"ok": True}


async def send_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
