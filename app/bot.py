import asyncio
import inspect
import os
import re
from dataclasses import dataclass
from typing import Optional

from aiohttp import web
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from yt_dlp import YoutubeDL


API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
STRING_SESSION = os.environ["STRING_SESSION"]
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
PORT = int(os.environ.get("PORT", "10011"))
YOUTUBE_COOKIES = os.environ.get("YOUTUBE_COOKIES", "")

if YOUTUBE_COOKIES:
    with open("cookies.txt", "w") as f:
        f.write(YOUTUBE_COOKIES)

YOUTUBE_OR_URL_RE = re.compile(r"^(https?://|ytsearch\d*:)", re.IGNORECASE)


@dataclass
class StreamInfo:
    title: str
    url: str
    webpage_url: str
    duration: Optional[int]


bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)
assistant = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
    in_memory=True,
)
calls = PyTgCalls(assistant)

queues: dict[int, list[StreamInfo]] = {}
now_playing: dict[int, StreamInfo] = {}
paused_chats: set[int] = set()


def command_arg(message: Message) -> str:
    if not message.text:
        return ""
    parts = message.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def is_allowed(message: Message) -> bool:
    if OWNER_ID and message.from_user and message.from_user.id == OWNER_ID:
        return True
    return not OWNER_ID


def pretty_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "live"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def ytdlp_extract(query: str, video: bool = False) -> StreamInfo:
    source = query if YOUTUBE_OR_URL_RE.match(query) else f"ytsearch1:{query}"

    ydl_opts = {
    "format": "best",

    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "default_search": "ytsearch1",
    "cookiefile": "cookies.txt",

    "extractor_args": {
        "youtube": {
            "player_client": ["android"]
        }
    },
}
    
    with YoutubeDL(ydl_opts) as ydl:
        data = ydl.extract_info(source, download=False)

    if "entries" in data:
        entries = [entry for entry in data.get("entries") or [] if entry]
        if not entries:
            raise ValueError("No YouTube result found.")
        data = entries[0]

    stream_url = data.get("url")
    if not stream_url:
        raise ValueError("No playable direct stream URL found.")

    return StreamInfo(
        title=data.get("title") or query,
        url=stream_url,
        webpage_url=data.get("webpage_url") or data.get("original_url") or query,
        duration=data.get("duration"),
    )


async def resolve_stream(query: str, video: bool = False) -> StreamInfo:
    return await asyncio.to_thread(ytdlp_extract, query, video)


def build_media_stream(info: StreamInfo, video: bool = False) -> AudioPiped:
    signature = inspect.signature(AudioPiped)
    kwargs = {}
    if "audio_flags" in signature.parameters:
        kwargs["audio_flags"] = AudioPiped.Flags.AUTO_DETECT
    if "video_flags" in signature.parameters:
        kwargs["video_flags"] = AudioPiped.Flags.AUTO_DETECT if video else AudioPiped.Flags.IGNORE
    return AudioPiped(info.url, **kwargs)


async def play_next(chat_id: int, video: bool = False) -> Optional[StreamInfo]:
    queue = queues.get(chat_id) or []
    if not queue:
        now_playing.pop(chat_id, None)
        return None
    info = queue.pop(0)
    await calls.play(chat_id, build_media_stream(info, video=video))
    now_playing[chat_id] = info
    paused_chats.discard(chat_id)
    return info


async def enqueue_or_play(message: Message, query: str, video: bool = False) -> None:
    if not query:
        await message.reply_text("Song name ba YouTube link dao.")
        return
    notice = await message.reply_text("YouTube stream khujchi...")
    try:
        info = await resolve_stream(query, video=video)
    except Exception as exc:
        await notice.edit_text(f"Stream pawa gelo na: `{exc}`")
        return

    chat_id = message.chat.id
    if chat_id in now_playing:
        queues.setdefault(chat_id, []).append(info)
        await notice.edit_text(
            f"Queued: **{info.title}**\nDuration: `{pretty_duration(info.duration)}`"
        )
        return

    queues.setdefault(chat_id, []).append(info)
    try:
        await play_next(chat_id, video=video)
    except Exception as exc:
        queues[chat_id].clear()
        now_playing.pop(chat_id, None)
        await notice.edit_text(f"VC te play start holo na: `{exc}`")
        return

    await notice.edit_text(
        f"Playing: **{info.title}**\nDuration: `{pretty_duration(info.duration)}`"
    )


async def ensure_group(message: Message) -> bool:
    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await message.reply_text("Eta group/supergroup-e use koro.")
        return False
    return True


@bot.on_message(filters.command(["start", "help"]))
async def start_handler(_, message: Message) -> None:
    await message.reply_text(
        "TG VC Music Bot ready.\n\n"
        "/play song name - audio play\n"
        "/vplay song name - video stream play\n"
        "/skip - next queue\n"
        "/pause - pause\n"
        "/resume - resume\n"
        "/end - stop and leave VC"
    )


@bot.on_message(filters.command("play") & filters.group)
async def play_handler(_, message: Message) -> None:
    if not await ensure_group(message):
        return
    await enqueue_or_play(message, command_arg(message), video=False)


@bot.on_message(filters.command("vplay") & filters.group)
async def vplay_handler(_, message: Message) -> None:
    if not await ensure_group(message):
        return
    await enqueue_or_play(message, command_arg(message), video=True)


@bot.on_message(filters.command("skip") & filters.group)
async def skip_handler(_, message: Message) -> None:
    chat_id = message.chat.id
    if not now_playing.get(chat_id):
        await message.reply_text("Ekhon kichu play hocche na.")
        return
    next_info = await play_next(chat_id)
    if next_info:
        await message.reply_text(f"Skipped. Now playing: **{next_info.title}**")
    else:
        await calls.leave_call(chat_id)
        await message.reply_text("Queue empty. VC theke ber hoye gelam.")


@bot.on_message(filters.command("pause") & filters.group)
async def pause_handler(_, message: Message) -> None:
    chat_id = message.chat.id
    if chat_id not in now_playing:
        await message.reply_text("Pause korar moto kichu cholche na.")
        return
    await calls.pause_stream(chat_id)
    paused_chats.add(chat_id)
    await message.reply_text("Paused.")


@bot.on_message(filters.command("resume") & filters.group)
async def resume_handler(_, message: Message) -> None:
    chat_id = message.chat.id
    if chat_id not in paused_chats:
        await message.reply_text("Paused stream nei.")
        return
    await calls.resume_stream(chat_id)
    paused_chats.discard(chat_id)
    await message.reply_text("Resumed.")


@bot.on_message(filters.command("end") & filters.group)
async def end_handler(_, message: Message) -> None:
    chat_id = message.chat.id
    queues.pop(chat_id, None)
    now_playing.pop(chat_id, None)
    paused_chats.discard(chat_id)
    await calls.leave_call(chat_id)
    await message.reply_text("Stopped and left VC.")


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner


async def start_services():
    await start_web_server()
    print("Web server started")

    await assistant.start()
    print("Assistant started")

    await calls.start()
    print("PyTgCalls started")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())

    print("Bot started")
    bot.run()
