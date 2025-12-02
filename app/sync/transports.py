# transports.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Callable

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

    def __init__(self, log: LogFunc, on_progress: ProgressCb) -> None:
        self._log = log
        self._on_progress = on_progress

    async def send_db(self, db_path: str) -> None:
        # Пока просто явно даём понять, что ещё не реализовано.
        if self._log:
            self._log("[webrtc] WebRTC transport is not implemented yet.")
        raise NotImplementedError("WebRTC sender transport not implemented yet")

    async def close(self) -> None:
        return
