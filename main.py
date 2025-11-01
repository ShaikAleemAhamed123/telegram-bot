from fastapi import FastAPI, Request, HTTPException
import httpx
from pytubefix import YouTube
import asyncio
import re

app = FastAPI()
BOT_TOKEN = "8311901559:AAEJIF3HbxtkVnf8YjVYQ5IBgAfcPl9Axh4"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.post("/hello")
async def webhook(request : Request):
    data = await request.json()
    print("Update received:", data)
    message = data.get("message",{})
    chat_id = message.get("chat",{}).get("id")
    text = message.get("text","")

    if chat_id:
        pattern = r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+(&\S*)?$"
        if re.match(pattern, text) is not None:
            # Download the video
            yt = YouTube(text)
            ys = yt.streams.get_highest_resolution()
            if ys:
                file_path = ys.download()
                if file_path:
                    # Send the video file to the chat
                    async with httpx.AsyncClient() as client:
                        with open(file_path, "rb") as video_file:
                            files = {"video": video_file}
                            data = {"chat_id": chat_id}
                            await client.post(f"{TELEGRAM_API}/sendVideo", data=data, files=files)
                    return {"ok": True, "message": "Video sent to chat."}
                else:
                    return {"ok": False, "error": "Video download failed (no file path returned)."}
            else:
                return {"ok": False, "error": "Unable to get the video metadata to download."}
        else:
            reply_text = f"You Said : {text}"
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text}
                )
    return {"ok": True}