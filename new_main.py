from fastapi import FastAPI, Request, BackgroundTasks
from pytubefix import YouTube
import httpx
import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
app = FastAPI()

BOT_TOKEN = os.environ.get("BOT_TOKEN","")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Telethon credentials
API_ID = int(os.environ.get("API_ID","0"))
API_HASH = os.environ.get("API_HASH","")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/bot")
async def download_video(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        url = message.get("text", "")
        
        if not url.startswith(("http://", "https://")) or ("youtube.com" not in url.lower() and "youtu.be" not in url.lower()):
            await send_message(chat_id, "❌ Please send a valid YouTube URL")
            return {"ok": True}
        
        background_tasks.add_task(process_video, chat_id, url)
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"ok": False}


from telethon.tl.types import DocumentAttributeVideo
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

async def process_video(chat_id: int, url: str):
    file_path = None
    try:
        await send_message(chat_id, "⏳ Downloading video...")
        
        yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
        stream = yt.streams.get_highest_resolution()
        if stream:
            file_path = stream.download()
        else:
            logger.error("No stream found for the video")
            return

        if file_path: 
            file_size = os.path.getsize(file_path)
            logger.info(f"File downloaded: {file_path}, Size: {file_size / (1024*1024):.2f} MB")
        else:
            logger.error("cannot find the path of the downloaded file")
            return
        
        # Extract video metadata
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        
        duration = int(metadata.get('duration').total_seconds()) if metadata and metadata.get('duration') else 0
        width = metadata.get('width') if metadata else 1280
        height = metadata.get('height') if metadata else 720
        
        logger.info(f"Video metadata - Duration: {duration}s, Resolution: {width}x{height}")
        
        await send_message(chat_id, f"📤 Uploading to Telegram... ({file_size / (1024*1024):.2f} MB)")
        
        client = TelegramClient("session", API_ID, API_HASH)
        client.start(bot_token=BOT_TOKEN)
        
        try:
            message = await client.send_file(
                entity=chat_id,
                file=file_path,
                caption=yt.title,
                attributes=[
                    DocumentAttributeVideo(
                        duration=duration,
                        w=width,
                        h=height,
                        supports_streaming=True
                    )
                ],
            )
            logger.info(f"Video sent successfully. Message ID: {message[0].id}")
            
        finally:
            client.disconnect()
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await send_message(chat_id, f"❌ Error: {str(e)}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", data={"chat_id": chat_id, "text": text})

@app.get("/")
async def root():
    return {"status": "Bot is running"}