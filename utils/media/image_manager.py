
from __future__ import annotations

import sys

from PyQt5.QtCore import QByteArray, QBuffer
from PyQt5.QtGui import QPixmap


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
