from pyrogram import Client
api_id = "AAPKA_API_ID_YAHAN" 
api_hash = "AAPKA_API_HASH_YAHAN"
with Client("my_account", api_id=api_id, api_hash=api_hash) as app:
    print(app.export_session_string())
