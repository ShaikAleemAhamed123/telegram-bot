from fastapi import FastAPI, Request, BackgroundTasks
from pytubefix import YouTube
import httpx
import os
import traceback
from typing import Set, Optional

app = FastAPI()
BOT_TOKEN = "8577277099:AAH-stXCaWNhNijfgIq0wfAsCcuyNlROBrQ"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# IMPORTANT: Create a channel and add your bot as admin, then put the channel ID here
# Channel ID format: @channelname or -100xxxxxxxxxx (for private channels)
STORAGE_CHANNEL_ID = "@your_storage_channel"  # Change this to your channel

# Track processed updates to prevent duplicates
processed_updates: Set[int] = set()

async def send_message(chat_id: int, text: str):
    """Helper to send text messages"""
    try:
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                data={"chat_id": chat_id, "text": text}
            )
            if response.status_code != 200:
                print(f"❌ Message send failed: {response.text}")
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        print(traceback.format_exc())
        return False

async def upload_to_channel(file_path: str, caption: str) -> Optional[str]:
    """Upload file to storage channel and return file_id"""
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"📤 Uploading {file_size_mb:.1f}MB to storage channel...")
        
        timeout = httpx.Timeout(connect=30.0, read=900.0, write=900.0, pool=30.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, "rb") as file:
                # For files > 50MB, use document. For <= 50MB, can use video
                if file_size_mb <= 50:
                    files = {"video": (os.path.basename(file_path), file, "video/mp4")}
                    endpoint = "sendVideo"
                else:
                    files = {"document": (os.path.basename(file_path), file, "video/mp4")}
                    endpoint = "sendDocument"
                
                data = {
                    "chat_id": STORAGE_CHANNEL_ID,
                    "caption": caption[:1024]
                }
                
                response = await client.post(
                    f"{TELEGRAM_API}/{endpoint}",
                    data=data,
                    files=files
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Extract file_id based on type
                    if endpoint == "sendVideo":
                        file_id = result["result"]["video"]["file_id"]
                    else:
                        file_id = result["result"]["document"]["file_id"]
                    
                    message_id = result["result"]["message_id"]
                    print(f"✅ Uploaded to channel! file_id: {file_id[:20]}...")
                    return file_id, message_id
                else:
                    print(f"❌ Channel upload failed ({response.status_code}): {response.text}")
                    return None, None
                    
    except Exception as e:
        print(f"❌ Error uploading to channel: {e}")
        print(traceback.format_exc())
        return None, None

async def forward_from_channel(chat_id: int, message_id: int) -> bool:
    """Forward message from storage channel to user"""
    try:
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{TELEGRAM_API}/forwardMessage",
                json={
                    "chat_id": chat_id,
                    "from_chat_id": STORAGE_CHANNEL_ID,
                    "message_id": message_id
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Forwarded message to user")
                return True
            else:
                print(f"❌ Forward failed: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error forwarding: {e}")
        return False

async def send_by_file_id(chat_id: int, file_id: str, caption: str, is_video: bool = True) -> bool:
    """Send file to user using file_id (without forwarding)"""
    try:
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            endpoint = "sendVideo" if is_video else "sendDocument"
            file_key = "video" if is_video else "document"
            
            response = await client.post(
                f"{TELEGRAM_API}/{endpoint}",
                json={
                    "chat_id": chat_id,
                    file_key: file_id,
                    "caption": caption[:1024]
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Sent file via file_id to user")
                return True
            else:
                print(f"❌ Send by file_id failed: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error sending by file_id: {e}")
        return False

async def process_video(chat_id: int, url: str):
    file_path = None
    
    try:
        yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
        print(f"🎬 Title: {yt.title}")
        
        # Get highest resolution stream
        ys = yt.streams.get_highest_resolution()
        if not ys:
            await send_message(chat_id, "❌ No streams available for this video")
            return
        
        # Download video
        await send_message(chat_id, "⬇️ Downloading video...")
        file_path = ys.download()
        print(f"✅ Downloaded: {file_path}")
        
        if not file_path or not os.path.exists(file_path):
            await send_message(chat_id, "❌ Download failed")
            return
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"📦 File size: {file_size_mb:.2f} MB")
        
        # Upload to storage channel first
        await send_message(chat_id, f"📤 Uploading to server ({file_size_mb:.1f} MB)...")
        
        is_video = file_size_mb <= 50
        file_id, message_id = await upload_to_channel(file_path, yt.title)
        
        if not file_id:
            await send_message(chat_id, "❌ Failed to upload to storage")
            return
        
        # Send to user (choose one method):
        
        # Method 1: Forward from channel (shows "Forwarded from Channel Name")
        # success = await forward_from_channel(chat_id, message_id)
        
        # Method 2: Send by file_id (appears as if bot sent it directly)
        success = await send_by_file_id(chat_id, file_id, yt.title, is_video)
        
        if success:
            await send_message(chat_id, "✅ Video sent successfully!")
        else:
            await send_message(chat_id, "❌ Failed to send video")
    
    except Exception as e:
        print(f"❌ Error processing video: {e}")
        print(traceback.format_exc())
        await send_message(chat_id, f"❌ Error: {str(e)[:200]}")
    
    finally:
        # Cleanup local file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print("🗑️ Deleted local file")

@app.post("/hello")
async def download_video(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        # Get update_id to prevent duplicate processing
        update_id = data.get("update_id")
        if update_id in processed_updates:
            print(f"⚠️ Duplicate update {update_id} - skipping")
            return {"ok": True, "message": "Already processing"}
        
        print(f"📩 Update received: {data}")
        
        # Mark as processed
        if update_id:
            processed_updates.add(update_id)
            # Keep only last 1000 update IDs to prevent memory growth
            if len(processed_updates) > 1000:
                processed_updates.pop()
        
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        url = message.get("text", "")
        
        if not chat_id or not url:
            return {"ok": False, "error": "Missing chat_id or url"}
        
        # Validate URL
        if not url.startswith(("http://", "https://")) or ("youtube.com" not in url and "youtu.be" not in url):
            await send_message(chat_id, "❌ Please send a valid YouTube URL")
            return {"ok": True}
        
        background_tasks.add_task(process_video, chat_id, url)
        
        return {"ok": True}
    
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        print(traceback.format_exc())
        return {"ok": False, "error": str(e)}

@app.get("/")
async def root():
    return {"status": "Bot is running", "note": "Set STORAGE_CHANNEL_ID in code"}