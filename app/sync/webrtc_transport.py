# webrtc_transport.py
from __future__ import annotations

import asyncio
import json
from typing import Optional, Callable

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc import RTCDataChannel

LogFunc = Optional[Callable[[str], None]]

class WebRTCSignalingError(Exception):
    pass

class WebRTCSenderCore:
    """
    Core для роли отправителя:
      - создаёт RTCPeerConnection
      - поднимает DataChannel "db"
      - генерит offer (JSON-строка)
      - принимает answer (JSON-строка)
      - ждёт ICE + открытие канала
    """

    def __init__(self, log: LogFunc = None) -> None:
        self._log = log or (lambda s: None)
        self._pc: Optional[RTCPeerConnection] = None
        self._channel: Optional[RTCDataChannel] = None
        self._connected = asyncio.Event()

    async def create_offer(self) -> str:
        from aiortc import RTCPeerConnection

        pc = RTCPeerConnection()
        self._pc = pc

        # создаём datachannel заранее
        channel = pc.createDataChannel("db")
        self._channel = channel

        @channel.on("open")
        def _on_open():
            self._log("[webrtc] datachannel 'db' opened")
            self._connected.set()

        @pc.on("iceconnectionstatechange")
        def _on_state_change():
            self._log(f"[webrtc] ICE state: {pc.iceConnectionState}")
            if pc.iceConnectionState in ("failed", "disconnected", "closed"):
                if not self._connected.is_set():
                    self._connected.set()

        # SDP offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # упаковываем SDP в JSON-строку
        payload = {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp,
        }
        s = json.dumps(payload, indent=2)
        self._log("[webrtc] Offer created")
        return s

    async def accept_answer(self, answer_sdp: str) -> None:
        if not self._pc:
            raise WebRTCSignalingError("PeerConnection not created")

        try:
            data = json.loads(answer_sdp)
            desc = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        except Exception as e:
            raise WebRTCSignalingError(f"Bad answer JSON: {e}") from e

        await self._pc.setRemoteDescription(desc)
        self._log("[webrtc] Answer applied, waiting for connection…")

        # ждём пока откроется канал или ICE не рухнет
        await self._connected.wait()

        if not self._channel or self._channel.readyState != "open":
            raise WebRTCSignalingError("DataChannel not opened")

        self._log("[webrtc] WebRTC connected (sender side)")

    async def send_bytes(self, data: bytes) -> None:
        if not self._channel or self._channel.readyState != "open":
            raise WebRTCSignalingError("Channel is not open")
        self._channel.send(data)

    async def close(self) -> None:
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._pc:
            await self._pc.close()
        self._channel = None
        self._pc = None
        self._connected.clear()

class WebRTCReceiverCore:
    """
    Core для роли приёмника:
      - получает offer (JSON-строка)
      - создаёт RTCPeerConnection, answer
      - ждёт datachannel "db"
    """

    def __init__(self, log: LogFunc = None) -> None:
        self._log = log or (lambda s: None)
        self._pc: Optional[RTCPeerConnection] = None
        self._channel: Optional[RTCDataChannel] = None
        self._connected = asyncio.Event()
        self._on_message: Optional[Callable[[bytes], None]] = None

    def set_on_message(self, cb: Callable[[bytes], None]) -> None:
        self._on_message = cb

    async def accept_offer_and_create_answer(self, offer_sdp: str) -> str:
        from aiortc import RTCPeerConnection, RTCSessionDescription

        pc = RTCPeerConnection()
        self._pc = pc

        @pc.on("datachannel")
        def _on_datachannel(ch: RTCDataChannel):
            self._log(f"[webrtc] datachannel received: {ch.label}")
            self._channel = ch

            @ch.on("open")
            def _on_open():
                self._log("[webrtc] datachannel 'db' opened (receiver)")
                self._connected.set()

            @ch.on("message")
            def _on_message(msg):
                if isinstance(msg, str):
                    msg_bytes = msg.encode("utf-8")
                else:
                    msg_bytes = msg
                if self._on_message:
                    self._on_message(msg_bytes)

        @pc.on("iceconnectionstatechange")
        def _on_state_change():
            self._log(f"[webrtc] ICE state: {pc.iceConnectionState}")
            if pc.iceConnectionState in ("failed", "disconnected", "closed"):
                if not self._connected.is_set():
                    self._connected.set()

        # парсим offer
        try:
            data = json.loads(offer_sdp)
            desc = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        except Exception as e:
            raise WebRTCSignalingError(f"Bad offer JSON: {e}") from e

        await pc.setRemoteDescription(desc)
        self._log("[webrtc] Offer applied, creating answer…")

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        payload = {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp,
        }
        s = json.dumps(payload, indent=2)
        self._log("[webrtc] Answer created")
        return s

    async def wait_connected(self) -> None:
        await self._connected.wait()
        if not self._channel or self._channel.readyState != "open":
            raise WebRTCSignalingError("DataChannel not opened")
        self._log("[webrtc] WebRTC connected (receiver side)")

    async def close(self) -> None:
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._pc:
            await self._pc.close()
        self._channel = None
        self._pc = None
        self._connected.clear()
