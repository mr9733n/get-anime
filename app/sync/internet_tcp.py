# internet_tcp.py
from __future__ import annotations

import socket
from pathlib import Path
from typing import Optional, Callable

from db_transfer import DBReceiver  # твой текущий класс

LogFunc = Optional[Callable[[str], None]]
ProgressCb = Optional[Callable[[int, int], None]]
SasConfirmCb = Optional[Callable[[str, str], bool]]
DoneCb = Optional[Callable[[str], None]]
InfoCb = Optional[Callable[[Optional[str], str, str], None]]

try:
    import stun  # pystun3
except Exception:
    stun = None

try:
    import miniupnpc
except Exception:
    miniupnpc = None


class InternetReceiver:
    """
    Обёртка вокруг DBReceiver:
      - STUN: определяем внешний IP и тип NAT
      - UPnP/NAT-PMP: пытаемся пробросить порт
      - INFO-callback для GUI (обновить External IP / NAT / UPnP status)
    """

    def __init__(
        self,
        *,
        port: int,
        chunk_dir: str,
        on_progress: ProgressCb,
        sas_confirm: SasConfirmCb,
        on_done: DoneCb,
        log: LogFunc,
        info_cb: InfoCb = None,
    ) -> None:
        self.port = int(port)
        self.chunk_dir = Path(chunk_dir)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        self._on_progress = on_progress
        self._sas_confirm = sas_confirm
        self._on_done = on_done
        self._log = log or (lambda s: print(s))
        self._info_cb = info_cb

        self._db_receiver: Optional[DBReceiver] = None
        self._upnp = None
        self._upnp_mapped = False

        self.external_ip: Optional[str] = None
        self.nat_type: str = "unknown"
        self.upnp_status: str = "not used"

    def _emit_info(self):
        if self._info_cb:
            try:
                self._info_cb(self.external_ip, self.nat_type, self.upnp_status)
            except Exception:
                pass

    def _run_stun(self):
        if not stun:
            self.nat_type = "unknown (pystun3 not installed)"
            self.external_ip = None
            self._log("[inet] STUN: library not available (pystun3)")
            return

        try:
            self._log("[inet] STUN: detecting external IP / NAT type…")
            nat_type, external_ip, external_port = stun.get_ip_info()
            self.nat_type = nat_type or "unknown"
            self.external_ip = external_ip
            self._log(f"[inet] STUN: NAT={self.nat_type}, external_ip={external_ip}, mapped_port={external_port}")
        except Exception as e:
            self.nat_type = "error"
            self.external_ip = None
            self._log(f"[inet] STUN: failed: {type(e).__name__}: {e}")

    def _run_upnp(self):
        if not miniupnpc:
            self.upnp_status = "miniupnpc not installed"
            self._log("[inet] UPnP: library not available (miniupnpc)")
            return

        try:
            self._log("[inet] UPnP: discovering IGD…")
            u = miniupnpc.UPnP()
            u.discoverdelay = 200
            ndevices = u.discover()
            if ndevices <= 0:
                self.upnp_status = "no IGD found"
                self._log("[inet] UPnP: no IGD found")
                return

            u.selectigd()
            self._upnp = u
            lan_ip = u.lanaddr
            ext_ip = u.externalipaddress()
            self._log(f"[inet] UPnP: IGD={lan_ip}, external_ip={ext_ip}")

            # Пытаемся пробросить self.port
            ok = u.addportmapping(
                self.port,
                "TCP",
                lan_ip,
                self.port,
                "PlayerDBSync InternetReceiver",
                "",
            )
            if ok:
                self._upnp_mapped = True
                self.upnp_status = f"mapped {self.port}/TCP"
                self._log(f"[inet] UPnP: port {self.port}/TCP mapped successfully")
            else:
                self.upnp_status = "mapping failed"
                self._log(f"[inet] UPnP: port {self.port}/TCP mapping failed")

        except Exception as e:
            self.upnp_status = f"error: {type(e).__name__}"
            self._log(f"[inet] UPnP: failed: {type(e).__name__}: {e}")

    async def start(self):
        """
        Запуск:
          1) STUN → нат, внешний IP
          2) UPnP → проброс порта (если возможно)
          3) DBReceiver.start_listen(host=0.0.0.0, mdns_advertise=False)
        """
        self._log(f"[inet] Starting InternetReceiver on port {self.port} …")
        self._run_stun()
        self._run_upnp()
        self._emit_info()

        self._db_receiver = DBReceiver(
            host="0.0.0.0",
            port=self.port,
            chunk_dir=str(self.chunk_dir),
            on_progress=self._on_progress,
            sas_confirm=self._sas_confirm,
            on_done=self._on_done,
            log=self._log,
            mdns_advertise=False,  # в интернет-режиме mDNS не нужен
        )
        await self._db_receiver.start_listen()

    async def stop(self):
        self._log("[inet] Stopping InternetReceiver …")
        if self._db_receiver:
            try:
                await self._db_receiver.stop()
            except Exception as e:
                self._log(f"[inet] DBReceiver stop error: {e}")

        # Снимаем проброс порта, если был
        if self._upnp and self._upnp_mapped:
            try:
                self._upnp.deleteportmapping(self.port, "TCP")
                self._log(f"[inet] UPnP: port {self.port}/TCP unmapped")
            except Exception as e:
                self._log(f"[inet] UPnP: delete mapping failed: {type(e).__name__}: {e}")
        self._upnp = None
        self._upnp_mapped = False
