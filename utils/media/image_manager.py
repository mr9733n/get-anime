from __future__ import annotations

import sys
import hashlib

from io import BytesIO
from PIL import Image, ImageFilter

from PyQt5.QtCore import QByteArray, QBuffer
from PyQt5.QtGui import QPixmap

MIN_ORIGINAL_W = 455


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def make_small_poster(blob: bytes, target_w: int = 80) -> bytes:
    img = Image.open(BytesIO(blob))
    w, h = img.size
    new_h = int(h * target_w / w)
    img = img.resize((target_w, new_h), Image.LANCZOS)
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def normalize_poster_blob_if_needed(
    poster_blob: bytes,
    size_key: str,
    min_w: int = MIN_ORIGINAL_W,
) -> tuple[bytes, bool]:
    """
    Возвращает (blob, changed).
    Меняем blob ТОЛЬКО если:
      - size_key == 'original' AND width < min_w  -> апскейл + PNG
      - либо blob webp (и ты хочешь хранить PNG ради Qt5) -> PNG
    Во всех остальных случаях возвращаем исходные bytes.
    """
    if not poster_blob:
        return poster_blob, False

    # Быстрая проверка на webp по сигнатуре (RIFF....WEBP)
    is_webp = len(poster_blob) > 12 and poster_blob[0:4] == b"RIFF" and poster_blob[8:12] == b"WEBP"

    # Если не original и не webp — вообще ничего не делаем
    if size_key != "original" and not is_webp:
        return poster_blob, False

    # Открываем через PIL (делаем это только когда реально нужно)
    img = Image.open(BytesIO(poster_blob))

    w, h = img.size
    need_upscale = (size_key == "original" and w and w < min_w)

    # Если original, но уже >= min_w, и не webp — не трогаем
    if not need_upscale and not is_webp:
        return poster_blob, False

    # Конвертируем и/или ресайзим → сохраняем в PNG
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA") if "A" in img.mode else img.convert("RGB")

    if need_upscale:
        new_w = min_w
        new_h = int(h * (new_w / w))
        img = img.resize((new_w, new_h), resample=Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))

    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), True


def guess_mime(b: bytes) -> str:
    if not b:
        return "image/webp"
    if b.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/webp"


def convert_image(blob: bytes) -> bytes | None:
    """
    Convert any blob (e.g. WEBP) to PNG bytes using QPixmap.
    More compatible with Qt5 QTextBrowser.
    """
    try:
        if not blob:
            return None

        pixmap = QPixmap()
        if not pixmap.loadFromData(blob):
            return None

        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        if not buffer.open(QBuffer.WriteOnly):
            return None

        if not pixmap.save(buffer, "PNG"):
            return None

        return bytes(byte_array)

    except Exception as e:
        # хотя бы так, раз тут нет logger
        print(f"Error converting image: {e}", file=sys.stderr)
        return None
