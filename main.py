from fastapi import FastAPI, Request
import httpx
from pytubefix import YouTube
import os

app = FastAPI()
BOT_TOKEN = "8311901559:AAEJIF3HbxtkVnf8YjVYQ5IBgAfcPl9Axh4"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.post("/greet")
async def webhook(request : Request):
    data = await request.json()
    print("Update received:", data)
    message = data.get("message",{})
    chat_id = message.get("chat",{}).get("id")
    text = message.get("text","")

    if chat_id:
        reply_text = f"You Said : {text}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id":chat_id, "text":reply_text}
                
            )
    return {"ok": True}

@app.post("/hello")
async def get_video_info(request: Request):
    data = await request.json()
    print("Update received:", data)

    message = data.get("message",{})
    chat_id = message.get("chat",{}).get("id")
    url = message.get("text","")

    yt = YouTube(url, use_po_token=True, client="WEB")
    print(yt.title)

    ys = yt.streams.get_highest_resolution()

    if ys:
        file_path = ys.download()
        async with httpx.AsyncClient() as client:
            if file_path:
                with open(file_path,"rb") as video_file:
                    files = {"video":video_file}
                    data = {"chat_id":chat_id}
                    await client.post(f"{TELEGRAM_API}/sendVideo", data=data, files=files)

    else:
        print("Unable to get the video metadata to download")
    return {"ok": True}