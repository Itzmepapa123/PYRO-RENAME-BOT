from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import ForceReply

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db

from asyncio import sleep
from PIL import Image
import os, time
import re

def extract_episode_number(filename):
    # Regular expressions to match episode numbers in various formats
    episode_patterns = [
        r"EP(\d+)",  # Match "EP12", "EP05", etc.
        r"E(\d+)",   # Match "E12", "E05", etc.
        r"Episode (\d+)",  # Match "Episode 12", "Episode 05", etc.
        r"Ep(\d+)"  # Match "Ep12", "Ep05", etc.
    ]
    
    for pattern in episode_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name
    user_id = message.from_user.id
    
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sᴏʀʀy Bʀᴏ Tʜɪꜱ Bᴏᴛ Iꜱ Dᴏᴇꜱɴ'ᴛ Sᴜᴩᴩᴏʀᴛ Uᴩʟᴏᴀᴅɪɴɢ Fɪʟᴇꜱ Bɪɢɢᴇʀ Tʜᴀɴ 2Gʙ")

    file_template = await db.get_file_template(user_id)

    if file_template:
        # Extract episode number
        episode_number = extract_episode_number(filename)
        
        # Replace placeholders in the template
        new_name = file_template.format(episode=episode_number or "01")
        await message.reply_text(f"Renaming to {new_name}")
        
        await rename_and_upload(client, message, file, new_name)
    else:
        await message.reply_text(
            text="Pʟᴇᴀꜱᴇ Sᴇᴛ A Fɪʟᴇ Nᴀᴍᴇ Tᴇᴍᴩʟᴀᴛᴇ Usɪɴɢ /file Cᴏᴍᴍᴀɴᴅ",
            reply_to_message_id=message.id
        )


@Client.on_message(filters.command("file") & filters.private)
async def set_file_template(client, message):
    user_id = message.from_user.id
    text = message.text.split(' ', 1)
    
    if len(text) == 2:
        template = text[1]
        
        # Save the template to the database
        await db.set_file_template(user_id, template)
        await message.reply_text("Fɪʟᴇ Nᴀᴍᴇ Tᴇᴍᴩʟᴀᴛᴇ Sᴇᴛ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟy.")
    else:
        await message.reply_text("Pʟᴇᴀꜱᴇ Pʀᴏᴠɪᴅᴇ A Vᴀʟɪᴅ Tᴇᴍᴩʟᴀᴛᴇ.")


async def rename_and_upload(client, message, file, new_name):
    media = getattr(file, file.media.value)
    
    if not "." in new_name:
        if "." in media.file_name:
            extn = media.file_name.rsplit('.', 1)[-1]
        else:
            extn = "mkv"
        new_name = new_name + "." + extn

    # Directly upload as a document
    await upload_document(client, message, file, new_name)


async def upload_document(client, message, file, new_name):
    file_path = f"downloads/{new_name}"
    user_id = int(message.chat.id)
    media = getattr(file, file.media.value)

    ms = await message.reply("Tʀyɪɴɢ Tᴏ Dᴏᴡɴʟᴏᴀᴅɪɴɢ....")
    try:
        path = await client.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("Dᴏᴡɴʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ....", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(e)

    duration = 0
    try:
        metadata = extractMetadata(createParser(file_path))
        if metadata.has("duration"):
            duration = metadata.get('duration').seconds
    except:
        pass
    ph_path = None
    c_caption = await db.get_caption(message.chat.id)
    c_thumb = await db.get_thumbnail(message.chat.id)

    if c_caption:
        try:
            caption = c_caption.format(filename=new_name, filesize=humanbytes(media.file_size), duration=convert(duration))
        except Exception as e:
            return await ms.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")
    else:
        caption = f"**{new_name}**"

    if (media.thumbs or c_thumb):
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        else:
            ph_path = await client.download_media(media.thumbs[0].file_id)
        Image.open(ph_path).convert("RGB").save(ph_path)
        img = Image.open(ph_path)
        img.resize((320, 320))
        img.save(ph_path, "JPEG")

    await ms.edit("Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....")
    try:
        await client.send_document(
            message.chat.id,
            document=file_path,
            thumb=ph_path,
            caption=caption,
            progress=progress_for_pyrogram,
            progress_args=("Uᴩʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ....", ms, time.time()))
    except Exception as e:
        os.remove(file_path)
        if ph_path:
            os.remove(ph_path)
        return await ms.edit(f" Eʀʀᴏʀ {e}")

    await ms.delete()
    os.remove(file_path)
    if ph_path:
        os.remove(ph_path)
