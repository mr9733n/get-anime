# transports.py
from __future__ import annotations

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
        # Для TCP тут нечего закрывать. Оставлено для совместимости.
        return


class WebRTCSenderTransport(SenderTransportBase):
    """
    Заглушка под будущий WebRTC DataChannel.
    Потом здесь будет логика установления WebRTC-соединения
    и отправки чанков через datachannel.
    """

    def __init__(
        self,
        log: LogFunc,
        on_progress: ProgressCb,
        show_offer: Callable[[str], None],
        wait_for_answer: Callable[[], str],
    ) -> None:
        self._log = log
        self._on_progress = on_progress
        self._show_offer = show_offer
        self._wait_for_answer = wait_for_answer
        self._core = WebRTCSenderCore(log=log)

    async def send_db(self, db_path: str) -> None:
        """
        Пока: только WebRTC-handshake + тестовое сообщение.
        Потом сюда вкрутим реальную отправку БД поверх datachannel.
        """
        # 1) создаём offer
        if self._log:
            self._log("[webrtc] creating offer…")
        offer = await self._core.create_offer()

        # 2) показываем offer в GUI (в Text/Entry на вкладке Send)
        self._show_offer(offer)

        # 3) ждём answer от пользователя (GUI должен вернуть строку SDP)
        if self._log:
            self._log("[webrtc] waiting for answer from GUI…")
        answer_sdp = self._wait_for_answer()
        if not answer_sdp.strip():
            raise WebRTCSignalingError("Empty WebRTC answer")

        # 4) применяем answer и ждём подключения
        await self._core.accept_answer(answer_sdp)

        # 5) тестовое сообщение — пока без реальной отправки db_path
        if self._log:
            self._log("[webrtc] sending test message over DataChannel…")
        await self._core.send_bytes(b"hello from WebRTC sender")

        if self._log:
            self._log("[webrtc] test message sent; DB transfer over WebRTC is not implemented yet")
        # Тут можно либо просто завершить, либо позже вставить логику передачи БД


    async def close(self) -> None:
        return
