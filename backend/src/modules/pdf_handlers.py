import os
import shutil
from typing import List

from fastapi import UploadFile

UPLOAD_DIR = "./uploads"


def save_uploaded_files(files: List[UploadFile]) -> List[str]:
    """Saves uploaded files to the uploads directory and returns their file paths."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_paths = []
    for file in files:
        temp_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_paths.append(temp_path)
    return file_paths
