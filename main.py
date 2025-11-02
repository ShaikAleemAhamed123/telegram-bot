from fastapi import FastAPI, Request, BackgroundTasks
from pytubefix import YouTube
import httpx, os
import traceback
import aiofiles
from httpx import AsyncByteStream

app = FastAPI()
BOT_TOKEN = "8577277099:AAH-stXCaWNhNijfgIq0wfAsCcuyNlROBrQ"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def process_video(chat_id: int, url: str):
    try:
        yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
        print(f"🎬 Title: {yt.title}")
        ys = yt.streams.get_highest_resolution()

        if ys:
            file_path = ys.download()
            print(f"✅ Downloaded: {file_path}")

            if file_path:
                if os.path.getsize(file_path) > 49 * 1024 * 1024:
                    print("Video > 50 MB...")
                    os.remove(file_path)
                    return {"ok": False, "error": "Unable to send large file to chat"}

                timeout = httpx.Timeout(600.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    with open(file_path, "rb") as video_file:
                        files = {"video": ("video.mp4", video_file, "video/mp4")}
                        data = {"chat_id": chat_id}
                        response = await client.post(f"{TELEGRAM_API}/sendVideo", data=data, files=files)
                        print(f"📨 Telegram response: {response.text}")

                os.remove(file_path)
                print("🗑️ Deleted downloaded file.")
            else:
                print("Downloaded file path not found")

    except Exception as e:
        print(f"❌ Error processing video: {e}")
        print(traceback.format_exc())

@app.post("/hello")
async def download_video(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("Update received:", data)

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    url = message.get("text", "")

    if chat_id and url:
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELEGRAM_API}/sendMessage", data = {"chat_id":chat_id, "text":"Downloading your Video..."})
        background_tasks.add_task(process_video, chat_id, url)

    # ✅ Respond immediately to Telegram
    return {"ok": True}