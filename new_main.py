from fastapi import FastAPI, Request, BackgroundTasks
from pytubefix import YouTube
import httpx
import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
import json
from telethon.utils import pack_bot_file_id

load_dotenv()
app = FastAPI()

BOT_TOKEN = os.environ.get("BOT_TOKEN","")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CACHE_FILE = "cache.json"
# Telethon credentials
API_ID = int(os.environ.get("API_ID","0"))
API_HASH = os.environ.get("API_HASH","")

uploaded_videos: dict[str, str] = {}


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_cache():
    global uploaded_videos
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as cache:
                uploaded_videos = json.load(cache)
                logger.info(f"Cache loaded successfully - {len(uploaded_videos)} videos cached")
        else:
            logger.info("No cache file found. Starting with empty cache.")
            uploaded_videos = {}
    except json.JSONDecodeError as e:
        logger.error(f"Cache file is corrupted: {e}. Starting with empty cache.")
        uploaded_videos = {}
    except Exception as e:
        logger.error(f"Error loading cache: {e}", exc_info=True)
        uploaded_videos = {}



# Load cache on startup
load_cache()

def persist_cache():
    """Save cache to JSON file"""
    try:
        with open(CACHE_FILE, "w") as cache:
            json.dump(uploaded_videos, cache, indent=2)
        logger.debug("Cache persisted successfully")
    except Exception as e:
        logger.error(f"Error persisting cache: {e}", exc_info=True)


@app.post("/bot")
async def process_video(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        url = message.get("text", "")

        if not url.startswith(("http://", "https://")) or ("youtube.com" not in url.lower() and "youtu.be" not in url.lower()):
            await send_message(chat_id, "❌ Please send a valid YouTube URL")
            return {"ok": True}
        
        background_tasks.add_task(download_video, chat_id, url)
        return {"ok": True}
        
    except Exception as e:
        await send_message(chat_id, "❌ Error While Preparing Video Download")
        logger.error(f"Error while Preparing Video Download : {e}", exc_info=True)
        return {"ok": False}


async def download_video(chat_id: int, url: str):
    file_path = None
    try:
        if url in uploaded_videos:
            await send_message(chat_id, "Sending Cached Video...")
            await send_video(url=url,file_path=uploaded_videos.get(url),chat_id=chat_id) #pyright: ignore
        else:
            await send_message(chat_id, "⏳ Downloading video...")
            
            yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
            stream = yt.streams.get_highest_resolution()
            if stream:
                file_path = stream.download()
            else:
                logger.error("No stream found for the video")

            if file_path: 
                await send_video(url=url, file_path=file_path, chat_id=chat_id)
            else:
                logger.error("cannot find the path of the downloaded file")
        
    except Exception as e:
        logger.error(f"Error while Downloading Video : {e}", exc_info=True)
        await send_message(chat_id,"❌ Error while Downloading Video")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def send_video(url:str, file_path: str, chat_id: int):
    client = None
    try:
        client = TelegramClient("session", API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN) #pyright: ignore

        logger.info(f"Sending Video...")
        message = await client.send_file(
            entity=chat_id,
            file=file_path,
            force_document=False,
            supports_streaming=True
        )
        await send_message(chat_id, "Thank You for availing the bot service...")
        logger.info(message)
        logger.info(f"Video sent successfully.")

        document = message.media.document #pyright: ignore
        file_id = pack_bot_file_id(document)
        uploaded_videos[url]=file_id #pyright: ignore
        persist_cache()
    except Exception as e:
        logger.exception("Error Initiating Telegram Client")
    finally:
        if client:
            await client.disconnect() #pyright: ignore
            logger.info(client.is_connected())

            
async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", data={"chat_id": chat_id, "text": text})

@app.get("/")
def root():
    return {"status": "Bot is running"}