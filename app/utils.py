import os
import uuid
from pathlib import Path
from .config import UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_upload_file(upload_file, subdir=""):
    ext = os.path.splitext(upload_file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    dir_path = Path(UPLOAD_DIR) / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    with file_path.open("wb") as f:
        content = upload_file.file.read()
        f.write(content)
    return str(file_path)
