from fastapi import FastAPI, Request
import httpx
from pytubefix import YouTube

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
        reply_text = f"You Said : {text}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id":chat_id, "text":reply_text}
                
            )
    return {"ok": True}

@app.post("/download_video")
async def get_video_info(request: Request):
    data = await request.json()
    url = data.get("url")
    yt = YouTube(url)
    print(yt.title)
    ys = yt.streams.get_highest_resolution()
    if ys:
        ys.download()
    else:
        print("Unable to get the video metadata to download")
    return {"ok": True}