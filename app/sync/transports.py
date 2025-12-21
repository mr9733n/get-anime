# transports.py
from __future__ import annotations

import os, json
from abc import ABC, abstractmethod
from typing import Optional, Callable

from webrtc_transport import WebRTCSenderCore, WebRTCSignalingError
from db_transfer import DBSender

LogFunc = Optional[Callable[[str], None]]
ProgressCb = Optional[Callable[[int, int], None]]
SasInfoCb = Optional[Callable[[str, str], None]]


class SenderTransportBase(ABC):
    """
    Абстракция транспорта отправки БД.
    Сейчас только TCP, позже добавим WebRTCTransport.
    """

    @abstractmethod
    async def send_db(self, db_path: str) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        На будущее: WebRTC/доп. ресурсы.
        Для TCP-реализации можно оставить пустым.
        """
        ...


class TcpSenderTransport(SenderTransportBase):
    """
    Обёртка над текущим DBSender — без изменения протокола.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        chunk_size: int,
        speed_kbps: Optional[int],
        log: LogFunc,
        on_progress: ProgressCb,
        sas_info: SasInfoCb,
        use_gzip: bool,
        vacuum_snapshot: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = DBSender(
            chunk_size=chunk_size,
            throttle_kbps=speed_kbps,
            on_progress=on_progress,
            sas_info=sas_info,
            log=log,
            use_gzip=use_gzip,
            vacuum_snapshot=vacuum_snapshot,
        )

    async def send_db(self, db_path: str) -> None:
        await self._sender.connect_and_send(self._host, self._port, db_path)

    async def close(self) -> None:
        return


class WebRTCSenderTransport(SenderTransportBase):
    """
    WebRTC DataChannel - логика установления WebRTC-соединения и отправки чанков через datachannel.
    """
    def __init__(
        self,
        log: LogFunc,
        on_progress: ProgressCb,
        show_offer: Callable[[str], None],
        wait_for_answer: Callable[[], str],
        *,
        chunk_size: int = 2 * 1024 * 1024,  # MiB из GUI
    ) -> None:
        self._log = log
        self._on_progress = on_progress
        self._show_offer = show_offer
        self._wait_for_answer = wait_for_answer
        self._core = WebRTCSenderCore(log=log)
        self._chunk_size = max(1, int(chunk_size))

    async def send_db(self, db_path: str) -> None:
        try:
            if self._log:
                self._log("[webrtc] creating offer…")
            offer = await self._core.create_offer()
            self._show_offer(offer)

            if self._log:
                self._log("[webrtc] waiting for answer from GUI…")
            answer_sdp = self._wait_for_answer()
            if not answer_sdp.strip():
                raise WebRTCSignalingError("Empty WebRTC answer")

            await self._core.accept_answer(answer_sdp)

            # --- Мини-протокол: header + чанки ---
            if not os.path.exists(db_path):
                raise WebRTCSignalingError(f"DB file not found: {db_path}")

            total = os.path.getsize(db_path)
            name = os.path.basename(db_path)

            if self._log:
                self._log(f"[webrtc] start sending DB over DataChannel: {name} ({total} bytes)")

            # 1) Header (JSON)
            header_obj = {
                "kind": "header",
                "name": name,
                "size": total,
            }
            header_bytes = json.dumps(header_obj).encode("utf-8")
            await self._core.send_bytes(header_bytes)

            # 2) Raw chunks
            sent = 0
            chunk_size = self._chunk_size

            with open(db_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    await self._core.send_bytes(chunk)
                    sent += len(chunk)

                    if self._on_progress:
                        try:
                            self._on_progress(sent, total)
                        except Exception:
                            pass

            if self._log:
                self._log(f"[webrtc] DB sent over DataChannel: {sent}/{total} bytes")

        except WebRTCSignalingError as e:
            if self._log:
                self._log(f"[webrtc] failed: {e}. WebRTC не установился, используй режим Internet TCP.")
            raise

    async def close(self) -> None:
        # Аккуратно гасим WebRTC, чтобы aiortc не оставлял таски
        try:
            await self._core.close()
        except Exception:
            # на shutdown лишние трэйсы не нужны
            pass
