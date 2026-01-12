import os
import uuid
from supabase import create_client
from fastapi import UploadFile
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def upload_file_to_supabase(file: UploadFile, order_id: str):
    """Uploads a file to Supabase storage and returns the public URL."""
    file_bytes = file.file.read()
    file_ext = file.filename.split(".")[-1]

    timestamp = str(uuid.uuid4().hex)
    path = f"{order_id}_{timestamp}.{file_ext}"

    res = supabase.storage.from_("complaints").upload(path, file_bytes)

    if isinstance(res, dict) and res.get("error"):
        return None

    return supabase.storage.from_("complaints").get_public_url(path)