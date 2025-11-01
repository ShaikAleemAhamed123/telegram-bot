from fastapi import FastAPI, Request, HTTPException
import httpx
from pytubefix import YouTube
from pytubefix.exceptions import BotDetection
import asyncio
import re
import os

app = FastAPI()
BOT_TOKEN = "8311901559:AAEJIF3HbxtkVnf8YjVYQ5IBgAfcPl9Axh4"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Regex matches typical youtube.com/watch?v=… URLs (you may extend to youtu.be etc)
YT_URL_PATTERN = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"

@app.post("/hello")
async def webhook(request: Request):
    data = await request.json()
    print("Update received:", data)
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id:
        # nothing to do if we don't have a chat_id
        return {"ok": True}

    # If the text matches a YouTube URL
    if re.match(YT_URL_PATTERN, text):
        try:
            # Run YouTube initialization in separate thread to avoid blocking
            yt = await asyncio.to_thread(YouTube, text, use_po_token=True, client="WEB")
        except BotDetection:
            # YouTube has detected bot-traffic behaviour
            raise HTTPException(status_code=503, detail="YouTube blocked this request due to bot-detection. Try again later.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YouTube URL or fetch error: {str(e)}")

        # Get the highest resolution stream
        try:
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by("resolution").desc().first()
            if not stream:
                raise HTTPException(status_code=500, detail="Couldn't find a suitable video stream to download.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error selecting stream: {str(e)}")

        # Download the video (blocking) in a thread
        try:
            file_path = await asyncio.to_thread(stream.download)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Video download failed: {str(e)}")

        # Check file size before uploading (Telegram bots typically have size limits ~50 MB) :contentReference[oaicite:1]{index=1}
        try:
            if file_path:
                size_bytes = os.path.getsize(file_path)
                size_mb = size_bytes / (1024 * 1024)
                print(f"Downloaded file size: {size_mb:.2f} MB")
                if size_mb > 50:
                    # Delete the file maybe and respond with an error
                    if file_path:
                        os.remove(file_path)
                    raise HTTPException(status_code=413, detail="Video file size exceeds Telegram bot upload limit (~50 MB).")
        except OSError as e:
            print("Could not check file size:", e)

        # Send the video file to the chat
        try:
            async with httpx.AsyncClient() as client:
                if file_path:
                    with open(file_path, "rb") as video_file:
                        files = {"video": video_file}
                        data_payload = {"chat_id": chat_id}
                        await client.post(f"{TELEGRAM_API}/sendVideo", data=data_payload, files=files)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send video to Telegram: {str(e)}")
        finally:
            # Delete the local file to save space
            try:
                if file_path:
                    os.remove(file_path)
            except Exception as e:
                print("Warning: failed to remove downloaded file:", e)

        return {"ok": True, "message": "Video sent to chat."}

    else:
        # Not a YouTube URL → send normal text reply
        reply_text = f"You Said : {text}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text}
            )
        return {"ok": True}
