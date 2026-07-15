import os
import subprocess
from pyrogram import Client, filters

# Heroku Dashboard se values lega
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
# Sirf aapko allow karne ke liye aapka Telegram ID
ALLOWED_USER_ID = int(os.environ.get('USER_ID', 0))

# Pyrogram Client setup with Bot Token
app = Client(
    "classplus_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# filters.user(ALLOWED_USER_ID) ka matlab sirf aap bot ko use kar payenge
@app.on_message(filters.command("download") & filters.user(ALLOWED_USER_ID))
def download_video(client, message):
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            message.reply_text("Sahi format: /download <content_id>")
            return

        content_id = parts[1]
        output_name = f"{content_id}.mp4"

        status_msg = message.reply_text(f"⏳ Downloading start ho gayi hai for ID: {content_id} (Heroku par)...")

        # classplus-dl.sh ko run karna. CLASSPLUS_TOKEN env var Heroku se aayega
        cmd = f"bash ./classplus-dl.sh {content_id} {output_name}"
        subprocess.run(cmd, shell=True, check=True)

        status_msg.edit_text("✅ Download complete! Ab Telegram par upload kar raha hoon (Isme thoda time lagega)...")

        # Telegram par upload
        client.send_video(
            chat_id=message.chat.id,
            video=output_name,
            caption=f"🎥 Video ID: {content_id}",
            supports_streaming=True
        )

        status_msg.edit_text("🎉 Upload Successfully Completed!")

        # Heroku ka space bachane ke liye video delete karna zaroori hai
        os.remove(output_name)

    except Exception as e:
        message.reply_text(f"❌ Error aagaya: {str(e)}")
        # Agar file aadhi download hui thi toh use delete kar dein
        if 'output_name' in locals() and os.path.exists(output_name):
            os.remove(output_name)

# Start command ka reply
@app.on_message(filters.command("start") & filters.user(ALLOWED_USER_ID))
def start_cmd(client, message):
    message.reply_text("Bot is Ready! Send /download <content_id> to download your video.")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
