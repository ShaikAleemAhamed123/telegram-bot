from fastapi import FastAPI, Request, BackgroundTasks
from pytubefix import YouTube
import httpx
import os
import traceback
import subprocess
import logging
from typing import Set, Dict, List, Union
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI()
BOT_TOKEN = "8577277099:AAH-stXCaWNhNijfgIq0wfAsCcuyNlROBrQ"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
MAX_SIZE_MB = 2000  # Telegram allows up to 2GB with local API

# Track processed updates to prevent duplicates
processed_updates: Set[int] = set()

# Cache uploaded videos: {youtube_url: file_id or [file_id1, file_id2, ...]}
# uploaded_videos: Dict[str, Union[str, List[str]]] = {}
uploaded_videos : Dict[str, Dict[str, Union[str, List[str]]]] = {}

def split_video(file_path: str, chunk_size_mb: int = 45) -> list:
    """Split video into chunks using ffmpeg"""
    try:
        logger.info(f"Starting video split process for: {os.path.basename(file_path)}")
        
        chunk_size_bytes = chunk_size_mb * 1024 * 1024
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size <= chunk_size_bytes:
            logger.info(f"File size ({file_size_mb:.2f}MB) is within limit. No splitting needed.")
            return [file_path]

        logger.info(f"File size: {file_size_mb:.2f}MB exceeds {chunk_size_mb}MB. Splitting required.")
        
        base, ext = os.path.splitext(file_path)
        output_pattern = f"{base}_part%03d{ext}"
        
        logger.debug(f"Output pattern: {output_pattern}")
        
        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        
        logger.debug("Retrieving video duration using ffprobe")
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        num_chunks = int(file_size / chunk_size_bytes) + 1
        chunk_duration = duration / num_chunks
        
        logger.info(f"Video duration: {duration:.2f}s, will split into {num_chunks} chunks of ~{chunk_duration:.2f}s each")
        
        # Split using ffmpeg
        cmd = [
            "ffmpeg", "-i", file_path, "-c", "copy",
            "-map", "0", "-f", "segment",
            "-segment_time", str(chunk_duration),
            "-reset_timestamps", "1",
            output_pattern
        ]
        
        logger.info("Starting ffmpeg split process")
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("FFmpeg split completed successfully")
        
        # Find all generated chunks
        base_dir = os.path.dirname(file_path) or "."
        base_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        chunks = sorted([
            os.path.join(base_dir, f) 
            for f in os.listdir(base_dir) 
            if f.startswith(f"{base_name_without_ext}_part") and f.endswith(ext)
        ])
        
        if chunks:
            logger.info(f"Successfully found {len(chunks)} chunks: {[os.path.basename(c) for c in chunks]}")
        else:
            logger.error(f"No chunks found! Expected pattern: {base_name_without_ext}_part*{ext}")
            part_files = [f for f in os.listdir(base_dir) if 'part' in f.lower()]
            logger.debug(f"Files with 'part' in directory: {part_files}")
        
        return chunks
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg/FFprobe command failed: {e}")
        logger.debug(f"Command output: {e.output if hasattr(e, 'output') else 'N/A'}")
        return [file_path]
    except Exception as e:
        logger.error(f"Error splitting video: {e}", exc_info=True)
        return [file_path]

async def send_large_file(chat_id: int, file_path: str, caption: str = "", url: str = None):
    """Send file using document endpoint - splits if needed"""
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        file_ids = []  # Store file_ids for caching
        
        logger.info(f"Processing large file upload - Size: {file_size_mb:.2f}MB, Chat ID: {chat_id}")
        
        # If file is too large for direct upload, split it
        if file_size_mb > 50:
            logger.info(f"File exceeds 50MB limit. Initiating split process.")
            await send_message(chat_id, f"📦 File is {file_size_mb:.1f} MB. Splitting into parts...")
            
            chunks = split_video(file_path, chunk_size_mb=45)
            
            if len(chunks) == 1:  # Split failed, try direct upload anyway
                logger.warning("Video splitting failed or returned single chunk. Attempting direct upload.")
                file_id = await upload_file(chat_id, file_path, caption)
                if file_id and url:
                    uploaded_videos[url] = file_id
                    logger.info(f"Cached file_id for URL: {url[:50]}...")
                return file_id is not None
            
            logger.info(f"Video split into {len(chunks)} chunks. Starting upload sequence.")
            
            # Upload each chunk
            for idx, chunk in enumerate(chunks, 1):
                chunk_caption = f"{caption} - Part {idx}/{len(chunks)}" if len(chunks) > 1 else caption
                logger.info(f"Uploading chunk {idx}/{len(chunks)}: {os.path.basename(chunk)}")
                await send_message(chat_id, f"📤 Uploading part {idx}/{len(chunks)}...")
                
                file_id = await upload_file(chat_id, chunk, chunk_caption)
                
                if file_id:
                    file_ids.append(file_id)
                    logger.debug(f"Chunk {idx} uploaded successfully. File ID: {file_id[:20]}...")
                else:
                    logger.error(f"Failed to upload chunk {idx}/{len(chunks)}")
                
                # Clean up chunk immediately after upload
                if os.path.exists(chunk) and chunk != file_path:
                    os.remove(chunk)
                    logger.debug(f"Deleted chunk: {os.path.basename(chunk)}")
                
                if not file_id:
                    logger.error(f"Upload sequence failed at chunk {idx}. Aborting.")
                    return False
            
            # Cache all file_ids
            if url and file_ids:
                uploaded_videos[url] = file_ids
                logger.info(f"Successfully cached {len(file_ids)} file_ids for URL: {url[:50]}...")
            
            logger.info(f"All {len(chunks)} chunks uploaded successfully")
            return True
        else:
            logger.info(f"File size within 50MB limit. Uploading directly.")
            file_id = await upload_file(chat_id, file_path, caption)
            if file_id and url:
                uploaded_videos[url] = file_id
                logger.info(f"Cached file_id for URL: {url[:50]}...")
            return file_id is not None
                    
    except Exception as e:
        logger.error(f"Error in send_large_file: {e}", exc_info=True)
        return False

async def upload_file(chat_id: int, file_path: str, caption: str = ""):
    """Upload a single file to Telegram and return file_id"""
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(f"Uploading file to Telegram - Name: {os.path.basename(file_path)}, Size: {file_size_mb:.2f}MB")
        
        timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, "rb") as file:
                files = {"document": (os.path.basename(file_path), file, "application/octet-stream")}
                data = {"chat_id": chat_id}
                
                if caption:
                    data["caption"] = caption[:1024]

                logger.debug(f"Sending POST request to Telegram API: /sendDocument")
                response = await client.post(
                    f"{TELEGRAM_API}/sendDocument",
                    data=data,
                    files=files
                )
                
                if response.status_code == 200:
                    file_upload_res = response.json()
                    file_id = file_upload_res.get("result", {}).get("document", {}).get("file_id")
                    logger.info(f"File uploaded successfully - File ID: {file_id[:20]}..., Name: {os.path.basename(file_path)}")
                    return file_id
                else:
                    logger.error(f"Upload failed - Status: {response.status_code}, Response: {response.text}")
                    return None
                    
    except httpx.TimeoutException as e:
        logger.error(f"Upload timeout for file: {os.path.basename(file_path)} - {e}")
        return None
    except Exception as e:
        logger.error(f"Error uploading file {os.path.basename(file_path)}: {e}", exc_info=True)
        return None

async def send_cached_video(chat_id: int, file_data: Union[str, List[str]], title: str) -> bool:
    """Send video using cached file_id(s)"""
    try:
        logger.info(f"Sending cached video to chat {chat_id} - Title: {title[:50]}...")
        timeout = httpx.Timeout(30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Single file
            if isinstance(file_data, str):
                logger.debug(f"Sending single cached file - File ID: {file_data[:20]}...")
                response = await client.post(
                    f"{TELEGRAM_API}/sendDocument",
                    json={
                        "chat_id": chat_id,
                        "document": file_data,
                        "caption": f"♻️ {title}"
                    }
                )
                success = response.status_code == 200
                if success:
                    logger.info("Cached video sent successfully")
                else:
                    logger.error(f"Failed to send cached video - Status: {response.status_code}")
                return success
            
            # Multiple parts
            elif isinstance(file_data, list):
                logger.info(f"Sending {len(file_data)} cached parts")
                for idx, file_id in enumerate(file_data, 1):
                    logger.debug(f"Sending cached part {idx}/{len(file_data)} - File ID: {file_id[:20]}...")
                    response = await client.post(
                        f"{TELEGRAM_API}/sendDocument",
                        json={
                            "chat_id": chat_id,
                            "document": file_id,
                            "caption": f"♻️ {title} - Part {idx}/{len(file_data)}"
                        }
                    )
                    if response.status_code != 200:
                        logger.error(f"Failed to send cached part {idx}/{len(file_data)} - Status: {response.status_code}")
                        return False
                    logger.debug(f"Cached part {idx}/{len(file_data)} sent successfully")
                logger.info(f"All {len(file_data)} cached parts sent successfully")
                return True
        
        return False
                
    except Exception as e:
        logger.error(f"Error sending cached video: {e}", exc_info=True)
        return False

async def process_video(chat_id: int, url: str):
    file_path = None
    
    try:
        logger.info(f"Processing video request - Chat ID: {chat_id}, URL: {url[:50]}...")
        
        # Check if video was already uploaded
        if url in uploaded_videos:
            logger.info(f"Video found in cache for URL: {url[:50]}...")
            yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
            await send_message(chat_id, f"♻️ Found '{yt.title}' in cache! Sending instantly...")
            
            success = await send_cached_video(chat_id, uploaded_videos[url], yt.title)
            
            if success:
                await send_message(chat_id, "✅ Video sent from cache (no download needed)!")
                logger.info(f"Successfully sent cached video to chat {chat_id}")
            else:
                logger.warning(f"Cache send failed for URL: {url[:50]}... Will attempt re-download.")
                await send_message(chat_id, "❌ Cache send failed, will re-download...")
                # Remove from cache and try fresh download
                del uploaded_videos[url]
            
            if success:
                return
        
        logger.info("Initializing YouTube download")
        yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)
        logger.info(f"Video metadata retrieved - Title: {yt.title}")
        
        # Get highest resolution stream
        ys = yt.streams.get_highest_resolution()
        if not ys:
            logger.error(f"No streams available for video: {url}")
            await send_message(chat_id, "❌ No streams available for this video")
            return
        
        logger.info(f"Selected stream - Resolution: {ys.resolution}, Format: {ys.mime_type}")
        
        # Download video
        await send_message(chat_id, "⏳ Downloading video...")
        logger.info("Starting video download")
        file_path = ys.download()
        logger.info(f"Video downloaded successfully - Path: {file_path}")
        
        if not file_path or not os.path.exists(file_path):
            logger.error("Download failed - File path is invalid or file does not exist")
            await send_message(chat_id, "❌ Download failed")
            return
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(f"Downloaded file details - Size: {file_size_mb:.2f}MB, Path: {os.path.basename(file_path)}")
        
        # Handle based on file size
        if file_size_mb <= 50:
            logger.info("File size within 50MB limit. Sending as video with thumbnail support.")
            await send_message(chat_id, f"📤 Uploading video ({file_size_mb:.1f} MB)...")
            timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(file_path, "rb") as video_file:
                    files = {"video": (os.path.basename(file_path), video_file, "video/mp4")}
                    data = {"chat_id": chat_id, "caption": yt.title[:1024]}
                    
                    logger.debug("Sending video to Telegram API")
                    response = await client.post(f"{TELEGRAM_API}/sendVideo", data=data, files=files)
                    logger.info(f"Telegram API response - Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        # Cache the file_id
                        result = response.json()
                        file_id = result.get("result", {}).get("video", {}).get("file_id")
                        if file_id:
                            uploaded_videos[url] = file_id
                            logger.info(f"Video file_id cached for future requests - URL: {url[:50]}...")
                        
                        await send_message(chat_id, "✅ Video uploaded successfully!")
                        logger.info(f"Video upload completed successfully for chat {chat_id}")
                    else:
                        logger.error(f"Video upload failed - Status: {response.status_code}, Response: {response.text}")
                        await send_message(chat_id, f"❌ Upload failed: {response.status_code}")
        
        else:
            logger.info(f"File size ({file_size_mb:.2f}MB) exceeds 50MB. Initiating large file upload process.")
            await send_message(chat_id, f"📤 Uploading large file ({file_size_mb:.1f} MB)...")
            success = await send_large_file(chat_id, file_path, yt.title, url)
            
            if success:
                await send_message(chat_id, "✅ All parts uploaded successfully!")
                logger.info(f"Large file upload completed successfully for chat {chat_id}")
            else:
                logger.error(f"Large file upload failed for chat {chat_id}")
                await send_message(chat_id, "❌ Failed to upload file")
    
    except Exception as e:
        logger.error(f"Error processing video for chat {chat_id}: {e}", exc_info=True)
        await send_message(chat_id, f"❌ Error: {str(e)[:200]}")
    
    finally:
        # Cleanup - only remove main file, chunks are cleaned up individually
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up downloaded file: {os.path.basename(file_path)}")

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
        if not url.startswith(("http://", "https://")) or ("youtube.com" not in url.lower() and "youtu.be" not in url.lower()):
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
    return {"status": "Bot is running"}