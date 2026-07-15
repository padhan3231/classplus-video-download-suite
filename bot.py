import os
import subprocess
import signal
from pyrogram import Client, filters

# Heroku Dashboard se values lega
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ALLOWED_USER_ID = int(os.environ.get('USER_ID', 0))

app = Client("classplus_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- GLOBAL VARIABLES (Cancel manage karne ke liye) ---
active_processes = {}  # Background process ko track karega
cancel_flags = {}      # Bulk download ko rokne ka signal dega

# ==========================================
# 1. CANCEL COMMAND
# ==========================================
@app.on_message(filters.command("cancel") & filters.user(ALLOWED_USER_ID))
def cancel_command(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = True  # Bulk loop ko rokne ke liye True set kiya
    
    if user_id in active_processes:
        try:
            # Jo bash script (aur ffmpeg) chal raha hai usko completely kill karna
            os.killpg(os.getpgid(active_processes[user_id].pid), signal.SIGTERM)
            message.reply_text("🛑 Download immediately rok diya gaya hai!")
        except Exception as e:
            message.reply_text(f"⚠️ Cancel karne mein dikkat aayi: {e}")
    else:
        message.reply_text("Abhi koi active download nahi chal raha hai.")

# ==========================================
# 2. START COMMAND
# ==========================================
@app.on_message(filters.command("start") & filters.user(ALLOWED_USER_ID))
def start_cmd(client, message):
    message.reply_text("🤖 Bot is Ready!\n\nCommands:\n🔹 /download <id> (Single Video)\n🔹 Send .txt file (Bulk Video)\n🔹 /cancel (To stop any download)")

# ==========================================
# 3. SINGLE DOWNLOAD COMMAND
# ==========================================
@app.on_message(filters.command("download") & filters.user(ALLOWED_USER_ID))
def download_video(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False  # Reset flag
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            message.reply_text("Sahi format: /download <content_id>")
            return

        content_id = parts[1]
        output_name = f"{content_id}.mp4"

        status_msg = message.reply_text(f"⏳ Downloading start ho gayi hai for ID: {content_id} ...")

        cmd = f"bash ./classplus-dl.sh {content_id} {output_name}"
        
        # Process start karna aur background mein chalana
        process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
        active_processes[user_id] = process
        process.wait()  # Download khatam (ya cancel) hone tak wait karega

        active_processes.pop(user_id, None) # List se process hatao

        # Check karna ki Process Cancel toh nahi hua?
        if cancel_flags.get(user_id):
            status_msg.edit_text("🛑 Download Cancelled by User.")
            if os.path.exists(output_name):
                os.remove(output_name)
            return

        # Check karna ki Process Error se toh band nahi hua?
        if process.returncode != 0:
            status_msg.edit_text("❌ Download Fail ho gaya (Token expire ho sakta hai).")
            if os.path.exists(output_name):
                os.remove(output_name)
            return

        status_msg.edit_text("✅ Download complete! Ab Telegram par upload kar raha hoon...")

        client.send_video(
            chat_id=message.chat.id,
            video=output_name,
            caption=f"🎥 Video ID: {content_id}",
            supports_streaming=True
        )

        status_msg.edit_text("🎉 Upload Successfully Completed!")
        os.remove(output_name)

    except Exception as e:
        message.reply_text(f"❌ Error aagaya: {str(e)}")
        if 'output_name' in locals() and os.path.exists(output_name):
            os.remove(output_name)
        active_processes.pop(user_id, None)

# ==========================================
# 4. BULK DOWNLOAD (.TXT FILE)
# ==========================================
@app.on_message(filters.document & filters.user(ALLOWED_USER_ID))
def download_from_file(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False # Reset flag
    
    if not message.document.file_name.endswith('.txt'):
        message.reply_text("❌ Kripya sirf .txt file bhejein.")
        return

    status_msg = message.reply_text("📄 Text file receive ho gayi! IDs padh raha hoon...")
    
    try:
        file_path = client.download_media(message)
        with open(file_path, 'r') as f:
            content_ids = [line.strip() for line in f.readlines() if line.strip()]
        
        if not content_ids:
            status_msg.edit_text("❌ File khali hai ya IDs nahi mili.")
            os.remove(file_path)
            return

        status_msg.edit_text(f"✅ Total {len(content_ids)} IDs mili hain. Bulk download start ho raha hai...")
        success_count = 0
        
        for idx, cid in enumerate(content_ids, 1):
            
            # Har video start hone se pehle check karna ki CANCEL toh nahi kiya?
            if cancel_flags.get(user_id):
                message.reply_text("🛑 Bulk Download process permanently cancel kar diya gaya hai!")
                break
                
            progress_msg = message.reply_text(f"⏳ [{idx}/{len(content_ids)}] Downloading ID: {cid} ...")
            output_name = f"{cid}.mp4"
            
            try:
                cmd = f"bash ./classplus-dl.sh {cid} {output_name}"
                process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
                active_processes[user_id] = process
                process.wait()
                
                # Check agar beech mein kill kiya gaya
                if cancel_flags.get(user_id):
                    progress_msg.edit_text(f"🛑 [{idx}/{len(content_ids)}] Video ID: {cid} cancelled.")
                    if os.path.exists(output_name):
                        os.remove(output_name)
                    break

                if process.returncode != 0:
                    progress_msg.edit_text(f"❌ [{idx}/{len(content_ids)}] Failed to download {cid}. (Skipping)")
                    if os.path.exists(output_name):
                        os.remove(output_name)
                    continue

                progress_msg.edit_text(f"✅ [{idx}/{len(content_ids)}] Download complete! Uploading...")
                
                client.send_video(
                    chat_id=message.chat.id,
                    video=output_name,
                    caption=f"🎥 Video {idx}/{len(content_ids)} | ID: {cid}",
                    supports_streaming=True
                )
                progress_msg.delete()
                success_count += 1
                
                if os.path.exists(output_name):
                    os.remove(output_name)
                    
            except Exception as e:
                progress_msg.edit_text(f"❌ [{idx}/{len(content_ids)}] Error in ID {cid}: {str(e)}")
                if os.path.exists(output_name):
                    os.remove(output_name)
            finally:
                active_processes.pop(user_id, None)
                
        message.reply_text(f"🎉 Bulk Status: {success_count}/{len(content_ids)} videos upload ho gayi hain.")
        if os.path.exists(file_path):
            os.remove(file_path)
        
    except Exception as e:
        message.reply_text(f"❌ File process error: {str(e)}")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
