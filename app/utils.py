import os
import uuid

PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'photos')

def save_photo_file(file_bytes: bytes) -> str:
    if not os.path.exists(PHOTO_DIR):
        os.makedirs(PHOTO_DIR, exist_ok=True)  # Создаёт папку, если её нет

    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join(PHOTO_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(file_bytes)
    return filepath
