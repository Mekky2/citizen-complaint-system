from pathlib import Path
from uuid import UUID
import mimetypes

from fastapi import HTTPException, UploadFile, status

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "tickets"

MAX_SIZES = {
    "image": 10 * 1024 * 1024,
    "audio": 20 * 1024 * 1024,
    "video": 50 * 1024 * 1024,
}

ALLOWED_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "audio/mpeg": ("audio", ".mp3"),
    "audio/wav": ("audio", ".wav"),
    "audio/x-wav": ("audio", ".wav"),
    "audio/mp4": ("audio", ".m4a"),
    "audio/ogg": ("audio", ".ogg"),
    "audio/webm": ("audio", ".webm"),
    "video/mp4": ("video", ".mp4"),
    "video/webm": ("video", ".webm"),
    "video/quicktime": ("video", ".mov"),
}


def detect_type(content_type: str | None):
    item = ALLOWED_TYPES.get((content_type or "").lower())
    if not item:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media format",
        )
    return item


def validate_signature(data: bytes, content_type: str):
    signatures = {
        "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
        "audio/wav": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE",
        "audio/x-wav": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE",
        "audio/ogg": lambda b: b.startswith(b"OggS"),
        "audio/mpeg": lambda b: (
            b.startswith(b"ID3") or b[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
        ),
        "audio/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
        "video/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "video/quicktime": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "video/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
    }
    check = signatures.get(content_type)
    if not check or not check(data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its declared format",
        )


async def save_upload(file: UploadFile, ticket_id: UUID, media_id: UUID):
    content_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    media_type, extension = detect_type(content_type)
    max_size = MAX_SIZES[media_type]

    directory = UPLOAD_DIR / str(ticket_id)
    directory.mkdir(parents=True, exist_ok=True)

    destination = directory / f"{media_id}{extension}"
    temporary = directory / f"{media_id}.part"

    total = 0
    first_chunk = b""

    try:
        with temporary.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds the {max_size // (1024 * 1024)} MB limit",
                    )
                if not first_chunk:
                    first_chunk = chunk[:32]
                output.write(chunk)

        if total == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        validate_signature(first_chunk, content_type)
        temporary.replace(destination)

        return media_type, destination

    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def find_media_file(ticket_id: UUID, media_id: UUID) -> Path | None:
    directory = UPLOAD_DIR / str(ticket_id)
    if not directory.is_dir():
        return None

    matches = list(directory.glob(f"{media_id}.*"))
    return matches[0] if len(matches) == 1 and matches[0].is_file() else None


def get_media_content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
