# db_sync_gui.py
import tkinter as tk
import os, csv, json, socket, asyncio, threading, traceback

from pathlib import Path
from typing import Optional
from datetime import datetime
from tkinter import ttk, filedialog, messagebox

os.environ.setdefault("ZC_DISABLE_CYTHON", "1")
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

from db_merge import run_merge

try:
    from transports import WebRTCSenderTransport
    from webrtc_transport import WebRTCReceiverCore, WebRTCSignalingError
    HAS_WEBRTC = True
except Exception:
    WebRTCSenderTransport = None
    WebRTCReceiverCore = None
    WebRTCSignalingError = None
    HAS_WEBRTC = False

try:
    from transports import TcpSenderTransport
    from internet_tcp import InternetReceiver
    HAS_STUN = True
except Exception:
    from tranports_lan import TcpSenderTransportLan
    TcpSenderTransport = None
    InternetReceiver = None
    HAS_STUN = False

from db_transfer import DBReceiver, DBSender, TOFU_FILE, save_tofu

MDNS_SERVICE_TYPE = "_playersync._tcp.local."
CFG_PATH = Path.home() / ".player_db_gui.json"


def load_gui_cfg():
    try:
        if CFG_PATH.exists():
            return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"recent": [], "last_port": "8765", "chunk_size": "2", "speed_kbps": ""}

def save_gui_cfg(cfg: dict):
    try:
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CFG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, CFG_PATH)
    except Exception:
        pass

class AsyncioThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        try:
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        self.thread.join(timeout=1.5)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        if not HAS_WEBRTC and not HAS_STUN:
            self.title("AnimePlayer DB LAN Sync and Merge")
        else:
            self.title("AnimePlayer DB Sync and Merge")

        self.geometry("780x560")
        self['padx'] = 8
        self['pady'] = 8
        self._zc = None
        self._mdns_browser = None
        self._mdns_hosts = set()
        self.asyncio_thread = AsyncioThread()
        # Для разных режимов приёма
        self.receiver_mode = "lan"      # 'lan' или 'internet'
        self.receiver_tcp: Optional[DBReceiver] = None
        self.receiver_inet: Optional[InternetReceiver] = None
        self.receiver_running = False

        # Информация для Internet TCP режима
        self.internet_ext_ip = tk.StringVar(value="—")
        self.internet_nat_type = tk.StringVar(value="—")
        self.internet_upnp_status = tk.StringVar(value="—")

        # WebRTC (receive)
        self.webrtc_rx_core: Optional[WebRTCReceiverCore] = None
        self.webrtc_ice_status = tk.StringVar(value="idle")

        # WebRTC receive state (file transfer)
        self.webrtc_rx_meta = None      # dict с метаданными header
        self.webrtc_rx_file = None      # открытый файловый дескриптор
        self.webrtc_rx_received = 0     # сколько байт уже приняли

        # WebRTC (send) – ожидание Answer
        self._webrtc_answer_event = threading.Event()
        self._webrtc_answer_value: str = ""

        self.merge_running = False
        self._pending = []
        self._sas_event = None
        self.cfg = load_gui_cfg()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        # создаём вкладки Send/Receive заранее
        self.tab_send = ttk.Frame(self.nb)
        self.tab_recv = ttk.Frame(self.nb)

        self.nb.add(self.tab_send, text="Send")
        self.nb.add(self.tab_recv, text="Receive")

        # Прокручиваемые контейнеры внутри вкладок
        self.send_body = self._make_scrollable(self.tab_send)
        self.recv_body = self._make_scrollable(self.tab_recv)

        self._build_tab_send()
        self._build_tab_receive()
        self._build_tab_merge()
        self._build_tab_logs()

        self._log("Готово. Используйте вкладки Send/Receive. История адресов сохраняется в ~/.player_db_gui.json.")

    # ---------- Tabs ----------
    def _build_tab_send(self):
        # --- Receiver / target block ---
        target_grp = ttk.LabelFrame(self.send_body, text="Target")
        target_grp.pack(fill="x", pady=(10, 8), padx=4)

        top = ttk.Frame(target_grp)
        top.pack(fill="x", pady=(4, 2))
        ttk.Label(top, text="Receiver:").pack(side="left")
        self.cmb_host = ttk.Combobox(top, width=28, values=self.cfg.get("recent", []))
        self.cmb_host.pack(side="left", padx=(6, 10))
        self.cmb_host.set(self.cfg["recent"][0] if self.cfg.get("recent") else "192.168.0.50")

        ttk.Label(top, text="Port:").pack(side="left")
        self.entry_port_send = ttk.Entry(top, width=7)
        self.entry_port_send.pack(side="left", padx=(6, 10))
        self.entry_port_send.insert(0, self.cfg.get("last_port", "8765"))

        btns = ttk.Frame(target_grp)
        btns.pack(fill="x", pady=(2, 4))
        ttk.Button(btns, text="Send DB…", command=self._on_send).pack(side="right", padx=6)
        ttk.Button(btns, text="Check connection", command=self._on_check_conn).pack(side="right")

        # --- Transport mode (Send) + mDNS discovery ---
        row_modes = ttk.Frame(self.send_body)
        row_modes.pack(fill="x", pady=(6, 4))

        row_modes.columnconfigure(0, weight=1)
        row_modes.columnconfigure(1, weight=1)

        # Left: Transport
        trgrp = ttk.LabelFrame(row_modes, text="Transport")
        trgrp.grid(row=0, column=0, sticky="nsew", padx=(4, 4))

        # >>> СНАЧАЛА создаём переменную
        self.var_transport_send = tk.StringVar(value="tcp")

        # TCP радиокнопка
        ttk.Radiobutton(
            trgrp,
            text="TCP (LAN / Internet, текущий протокол)",
            value="tcp",
            variable=self.var_transport_send,
        ).pack(anchor="w", padx=4, pady=2)

        # WebRTC радиокнопка
        rb_webrtc_send = ttk.Radiobutton(
            trgrp,
            text="WebRTC (P2P, экспериментально)",
            value="webrtc",
            variable=self.var_transport_send,
        )
        rb_webrtc_send.pack(anchor="w", padx=4, pady=2)

        if not HAS_WEBRTC:
            rb_webrtc_send.config(state="disabled", text="WebRTC (not available in this build)")

        self._maybe_disable(rb_webrtc_send, HAS_WEBRTC, "WebRTC removed in LAN build")

        # Right: mDNS discovery
        mdgrp = ttk.LabelFrame(row_modes, text="LAN discovery (mDNS)")
        mdgrp.grid(row=0, column=1, sticky="nsew", padx=(4, 4))

        md = ttk.Frame(mdgrp)
        md.pack(fill="x", pady=(4, 2))
        ttk.Button(md, text="Find active on LAN (mDNS)", command=self._start_mdns_browse).pack(side="right")
        ttk.Button(md, text="Clear list", command=self._clear_mdns).pack(side="right", padx=(6, 0))

        self.mdns_status = tk.StringVar(value="mDNS: idle")
        ttk.Label(md, textvariable=self.mdns_status).pack(side="left", padx=10)

        # --- Settings + SAS (два столбца) ---
        row_cfg = ttk.Frame(self.send_body)
        row_cfg.pack(fill="x", pady=(6, 6))

        row_cfg.columnconfigure(0, weight=1)
        row_cfg.columnconfigure(1, weight=1)

        # Left: Settings
        setgrp = ttk.LabelFrame(row_cfg, text="Settings")
        setgrp.grid(row=0, column=0, sticky="nsew", padx=(4, 4))

        srow = ttk.Frame(setgrp)
        srow.pack(fill="x", pady=(6, 2))
        ttk.Label(srow, text="Chunk size (MiB):").pack(side="left")
        self.entry_chunk = ttk.Entry(srow, width=6)
        self.entry_chunk.pack(side="left", padx=(6, 16))
        self.entry_chunk.insert(0, self.cfg.get("chunk_size", "2"))

        self.chunk_human = tk.StringVar()
        ttk.Label(srow, textvariable=self.chunk_human).pack(side="left", padx=(6, 0))

        srow2 = ttk.Frame(setgrp)
        srow2.pack(fill="x", pady=(6, 2))
        ttk.Label(srow2, text="Speed limit (KB/s):").pack(side="left")
        self.entry_speed = ttk.Entry(srow2, width=10)
        self.entry_speed.pack(side="left", padx=(6, 0))
        self.entry_speed.insert(0, self.cfg.get("speed_kbps", ""))

        self.speed_human = tk.StringVar()
        ttk.Label(srow2, textvariable=self.speed_human).pack(side="left", padx=(6, 0))

        self.var_send_compress = tk.BooleanVar(value=self.cfg.get("compress_gzip", False))
        ttk.Checkbutton(
            setgrp,
            text="Compress snapshot (gzip)",
            variable=self.var_send_compress,
        ).pack(anchor="w", pady=(2, 2))

        self.var_send_vacuum = tk.BooleanVar(value=self.cfg.get("sender_vacuum", False))
        ttk.Checkbutton(
            setgrp,
            text="VACUUM snapshot before send",
            variable=self.var_send_vacuum,
        ).pack(anchor="w", pady=(0, 2))

        self.entry_chunk.bind(
            "<KeyRelease>",
            lambda e: self._update_human(self.entry_chunk, self.chunk_human, "chunk"),
        )
        self.entry_speed.bind(
            "<KeyRelease>",
            lambda e: self._update_human(self.entry_speed, self.speed_human, "speed"),
        )

        self.after(100, lambda: self._update_human(self.entry_chunk, self.chunk_human, "chunk"))
        self.after(100, lambda: self._update_human(self.entry_speed, self.speed_human, "speed"))

        # Snapshot management
        srow3 = ttk.Frame(setgrp)
        srow3.pack(fill="x", pady=(8, 2))
        ttk.Button(srow3, text="Delete snapshot", command=self._delete_snapshot).pack(side="right")

        # Right: SAS (sender)
        sasgrp = ttk.LabelFrame(row_cfg, text="SAS (sender)")
        sasgrp.grid(row=0, column=1, sticky="nsew", padx=(4, 4))

        row1 = ttk.Frame(sasgrp)
        row1.pack(fill="x", pady=(6, 2))
        ttk.Label(row1, text="SAS:").pack(side="left")
        self.send_sas_code = tk.StringVar(value="—")
        ttk.Label(row1, textvariable=self.send_sas_code, font=("TkDefaultFont", 12, "bold")).pack(
            side="left", padx=6
        )

        row2 = ttk.Frame(sasgrp)
        row2.pack(fill="x", pady=(2, 8))
        ttk.Label(row2, text="FP:").pack(side="left")
        self.send_sas_fp = tk.StringVar(value="—")
        ttk.Label(row2, textvariable=self.send_sas_fp).pack(side="left", padx=6)

        # ---- WebRTC signaling (Send) ----
        webrtc_grp = ttk.LabelFrame(self.send_body, text="WebRTC signaling (experimental)")
        webrtc_grp.pack(fill="both", expand=False, pady=(4, 6), padx=4)

        # === Offer (collapsible) ===
        offer_frame = ttk.Frame(webrtc_grp)
        offer_frame.pack(fill="x", pady=(2, 2))

        offer_hdr = ttk.Frame(offer_frame)
        offer_hdr.pack(fill="x")

        offer_toggle = ttk.Label(offer_hdr, text="►", cursor="hand2")
        offer_toggle.pack(side="left", padx=(0, 4))

        ttk.Label(offer_hdr, text="Offer (sender → receiver):").pack(side="left")

        ttk.Button(
            offer_hdr,
            text="Copy",
            command=lambda: self._copy_text(self.webrtc_offer),
        ).pack(side="right", padx=(4, 0))

        ttk.Button(
            offer_hdr,
            text="Clear",
            command=lambda: self._clear_text(self.webrtc_offer),
        ).pack(side="right")

        offer_body = ttk.Frame(offer_frame)
        offer_body.pack(fill="both", expand=True, pady=(2, 4))

        self.webrtc_offer = tk.Text(offer_body, height=8, wrap="word")
        self.webrtc_offer.pack(fill="both", expand=True)

        # по умолчанию скрыто
        offer_body.pack_forget()
        offer_state = {"open": False}

        def toggle_offer():
            if offer_state["open"]:
                offer_body.pack_forget()
                offer_toggle.config(text="►")
                offer_state["open"] = False
            else:
                offer_body.pack(fill="both", expand=True, pady=(2, 4))
                offer_toggle.config(text="▼")
                offer_state["open"] = True

        offer_toggle.bind("<Button-1>", lambda e: toggle_offer())
        offer_hdr.bind("<Button-1>", lambda e: toggle_offer())

        # === Answer (collapsible) ===
        answer_frame = ttk.Frame(webrtc_grp)
        answer_frame.pack(fill="x", pady=(2, 2))

        answer_hdr = ttk.Frame(answer_frame)
        answer_hdr.pack(fill="x")

        answer_toggle = ttk.Label(answer_hdr, text="►", cursor="hand2")
        answer_toggle.pack(side="left", padx=(0, 4))

        ttk.Label(answer_hdr, text="Answer (receiver → sender):").pack(side="left")

        ttk.Button(
            answer_hdr,
            text="Paste",
            command=lambda: self._paste_text(self.webrtc_answer),
        ).pack(side="right", padx=(4, 0))

        ttk.Button(
            answer_hdr,
            text="Clear",
            command=lambda: self._clear_text(self.webrtc_answer),
        ).pack(side="right")

        answer_body = ttk.Frame(answer_frame)
        answer_body.pack(fill="both", expand=True, pady=(2, 4))

        self.webrtc_answer = tk.Text(answer_body, height=8, wrap="word")
        self.webrtc_answer.pack(fill="both", expand=True)

        answer_body.pack_forget()
        answer_state = {"open": False}

        def toggle_answer():
            if answer_state["open"]:
                answer_body.pack_forget()
                answer_toggle.config(text="►")
                answer_state["open"] = False
            else:
                answer_body.pack(fill="both", expand=True, pady=(2, 4))
                answer_toggle.config(text="▼")
                answer_state["open"] = True

        answer_toggle.bind("<Button-1>", lambda e: toggle_answer())
        answer_hdr.bind("<Button-1>", lambda e: toggle_answer())

        # === Bottom: кнопка применения Answer ===
        row_btn = ttk.Frame(webrtc_grp)
        row_btn.pack(fill="x", pady=(4, 4))

        webrtc_connect_btn = ttk.Button(
            row_btn,
            text="Use Answer / connect",
            command=self._on_webrtc_use_answer,
        )
        webrtc_connect_btn.pack(side="right", padx=(0, 4))
        self._maybe_disable(webrtc_connect_btn, HAS_WEBRTC, "WebRTC removed in LAN build")

        # Progress
        self.prog_send = ttk.Progressbar(self.send_body, length=400, mode="determinate")
        self.prog_send.pack(fill="x", pady=(10, 10))

    def _build_tab_receive(self):
        row = ttk.Frame(self.recv_body)
        row.pack(fill="x", pady=(10, 6))

        # Две равные колонки
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        # Transport mode (Receive)
        trgrp = ttk.LabelFrame(row, text="Transport")
        trgrp.pack(side="left", fill="both", expand=True, padx=4)
        self.var_transport_recv = tk.StringVar(value="tcp")

        ttk.Radiobutton(
            trgrp,
            text="TCP (LAN / Internet, текущий протокол)",
            value="tcp",
            variable=self.var_transport_recv,
        ).pack(anchor="w", padx=4, pady=2)

        rb_webrtc_recv = ttk.Radiobutton(
            trgrp,
            text="WebRTC (P2P, экспериментально)",
            value="webrtc",
            variable=self.var_transport_recv,
        )
        rb_webrtc_recv.pack(anchor="w", padx=4, pady=2)
        self._maybe_disable(rb_webrtc_recv, HAS_WEBRTC, "WebRTC removed in LAN build")

        # TCP подрежим: LAN vs Internet
        tcpgrp = ttk.LabelFrame(row, text="TCP mode")
        tcpgrp.pack(side="left", fill="both", expand=True, padx=4)

        self.var_tcp_mode_recv = tk.StringVar(value="lan")
        ttk.Radiobutton(
            tcpgrp,
            text="LAN (локальная сеть, mDNS)",
            value="lan",
            variable=self.var_tcp_mode_recv,
        ).pack(anchor="w", padx=4, pady=2)
        rb_stun_recv = ttk.Radiobutton(
            tcpgrp,
            text="Internet (STUN + UPnP, без mDNS)",
            value="internet",
            variable=self.var_tcp_mode_recv,
        )
        rb_stun_recv.pack(anchor="w", padx=4, pady=2)
        self._maybe_disable(rb_stun_recv, HAS_STUN, "Internet mode disabled in LAN build")

        # --- Server control block ---
        server_grp = ttk.LabelFrame(self.recv_body, text="Server control")
        server_grp.pack(fill="x", pady=(6, 8), padx=4)

        # строка со статусом и LED
        row = ttk.Frame(server_grp)
        row.pack(fill="x", pady=(2, 2))

        self.recv_led = tk.Canvas(row, width=14, height=14, highlightthickness=0)
        self.recv_led.pack(side="left", padx=(0, 6))
        self._recv_led_id = self.recv_led.create_oval(
            2, 2, 12, 12,
            fill="#d9534f", outline="#a94442"  # red
        )

        self.recv_status = tk.StringVar(value="Server: Stopped")
        ttk.Label(row, textvariable=self.recv_status).pack(side="left")

        # строка с портом
        row_port = ttk.Frame(server_grp)
        row_port.pack(fill="x", pady=(2, 2))

        ttk.Label(row_port, text="Listen port:").pack(side="left")
        self.entry_port_recv = ttk.Entry(row_port, width=7)
        self.entry_port_recv.pack(side="left", padx=(6, 10))
        self.entry_port_recv.insert(0, self.cfg.get("last_port", "8765"))

        # строка с кнопками (вместе)
        btn_row = ttk.Frame(server_grp)
        btn_row.pack(fill="x", pady=(2, 4))

        ttk.Button(
            btn_row,
            text="Reset TOFU (forget all)",
            command=self._reset_tofu,
        ).pack(side="right")

        ttk.Button(
            btn_row,
            text="Start / Stop",
            command=self._on_toggle_receive,
        ).pack(side="right", padx=(6, 0))

        # --- Два блока в одной строке ---
        row1 = ttk.Frame(self.recv_body)
        row1.pack(fill="x", pady=(10, 6))

        # Две равные колонки
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        # ========== Left block: SAS confirmation ==========
        sasfrm = ttk.LabelFrame(row1, text="SAS confirmation")
        sasfrm.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        row_in1 = ttk.Frame(sasfrm)
        row_in1.pack(fill="x", pady=(6, 2))
        ttk.Label(row_in1, text="SAS:").pack(side="left")
        self.recv_sas_code = tk.StringVar(value="—")
        ttk.Label(row_in1, textvariable=self.recv_sas_code, font=("TkDefaultFont", 12, "bold")).pack(side="left",
                                                                                                     padx=6)

        row_in2 = ttk.Frame(sasfrm)
        row_in2.pack(fill="x", pady=(2, 10))
        ttk.Label(row_in2, text="FP:").pack(side="left")
        self.recv_sas_fp = tk.StringVar(value="—")
        ttk.Label(row_in2, textvariable=self.recv_sas_fp).pack(side="left", padx=6)

        btns = ttk.Frame(sasfrm)
        btns.pack(pady=(0, 8))
        ttk.Button(btns, text="Accept", command=self._sas_accept).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self._sas_reject).pack(side="left", padx=6)

        # ========== Right block: Internet info ==========
        inetgrp = ttk.LabelFrame(row1, text="Internet info (TCP)")
        inetgrp.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        rowi1 = ttk.Frame(inetgrp)
        rowi1.pack(fill="x", pady=2)
        ttk.Label(rowi1, text="External IP:").pack(side="left")
        ttk.Label(rowi1, textvariable=self.internet_ext_ip).pack(side="left", padx=4)

        rowi2 = ttk.Frame(inetgrp)
        rowi2.pack(fill="x", pady=2)
        ttk.Label(rowi2, text="NAT type:").pack(side="left")
        ttk.Label(rowi2, textvariable=self.internet_nat_type).pack(side="left", padx=4)

        rowi3 = ttk.Frame(inetgrp)
        rowi3.pack(fill="x", pady=2)
        ttk.Label(rowi3, text="UPnP:").pack(side="left")
        ttk.Label(rowi3, textvariable=self.internet_upnp_status).pack(side="left", padx=4)

        stun_activity_btn = ttk.Button(
            inetgrp,
            text="Check external availability",
            command=self._on_check_internet_port,
        )
        stun_activity_btn.pack(anchor="w", pady=(4, 0))
        self._maybe_disable(stun_activity_btn, HAS_STUN, "Internet mode disabled in LAN build")

        # ---- WebRTC signaling (Receive) ----
        webrtc_grp = ttk.LabelFrame(self.recv_body, text="WebRTC signaling (experimental)")
        webrtc_grp.pack(fill="both", expand=True, pady=(4, 4), padx=4)

        # === Offer (collapsible) ===
        offer_frame = ttk.Frame(webrtc_grp)
        offer_frame.pack(fill="x", pady=(2, 2))

        offer_hdr = ttk.Frame(offer_frame)
        offer_hdr.pack(fill="x")

        offer_toggle = ttk.Label(offer_hdr, text="►", cursor="hand2")
        offer_toggle.pack(side="left", padx=(0, 4))

        ttk.Label(offer_hdr, text="Offer (sender → receiver):").pack(side="left")

        ttk.Button(
            offer_hdr,
            text="Paste",
            command=lambda: self._paste_text(self.webrtc_offer_recv),
        ).pack(side="right", padx=(4, 0))

        ttk.Button(
            offer_hdr,
            text="Clear",
            command=lambda: self._clear_text(self.webrtc_offer_recv),
        ).pack(side="right")

        offer_body = ttk.Frame(offer_frame)
        offer_body.pack(fill="both", expand=True, pady=(2, 4))

        self.webrtc_offer_recv = tk.Text(offer_body, height=8, wrap="word")
        self.webrtc_offer_recv.pack(fill="both", expand=True)

        # по умолчанию скрыто
        offer_body.pack_forget()
        offer_state = {"open": False}

        def toggle_offer():
            if offer_state["open"]:
                offer_body.pack_forget()
                offer_toggle.config(text="►")
                offer_state["open"] = False
            else:
                offer_body.pack(fill="both", expand=True, pady=(2, 4))
                offer_toggle.config(text="▼")
                offer_state["open"] = True

        offer_toggle.bind("<Button-1>", lambda e: toggle_offer())
        offer_hdr.bind("<Button-1>", lambda e: toggle_offer())

        # === Answer (collapsible) ===
        answer_frame = ttk.Frame(webrtc_grp)
        answer_frame.pack(fill="x", pady=(2, 2))

        answer_hdr = ttk.Frame(answer_frame)
        answer_hdr.pack(fill="x")

        answer_toggle = ttk.Label(answer_hdr, text="►", cursor="hand2")
        answer_toggle.pack(side="left", padx=(0, 4))

        ttk.Label(answer_hdr, text="Answer (receiver → sender):").pack(side="left")

        (ttk.Button(
            answer_hdr,
            text="Copy",
            command=lambda: self._copy_text(self.webrtc_answer_recv),
        ).pack(side="right", padx=(4, 0)))

        ttk.Button(
            answer_hdr,
            text="Clear",
            command=lambda: self._clear_text(self.webrtc_answer_recv),
        ).pack(side="right")

        answer_body = ttk.Frame(answer_frame)
        answer_body.pack(fill="both", expand=True, pady=(2, 4))

        self.webrtc_answer_recv = tk.Text(answer_body, height=8, wrap="word")
        self.webrtc_answer_recv.pack(fill="both", expand=True)

        answer_body.pack_forget()
        answer_state = {"open": False}

        def toggle_answer():
            if answer_state["open"]:
                answer_body.pack_forget()
                answer_toggle.config(text="►")
                answer_state["open"] = False
            else:
                answer_body.pack(fill="both", expand=True, pady=(2, 4))
                answer_toggle.config(text="▼")
                answer_state["open"] = True

        answer_toggle.bind("<Button-1>", lambda e: toggle_answer())
        answer_hdr.bind("<Button-1>", lambda e: toggle_answer())

        # === Bottom row: ICE + Apply ===
        row_ctrl = ttk.Frame(webrtc_grp)
        row_ctrl.pack(fill="x", pady=(4, 2))

        ttk.Label(row_ctrl, text="ICE:").pack(side="left")
        ttk.Label(row_ctrl, textvariable=self.webrtc_ice_status).pack(side="left", padx=(4, 0))

        webrtc_apply_offer_btn = ttk.Button(
            row_ctrl,
            text="Apply offer / create answer",
            command=self._webrtc_apply_offer,
        )
        webrtc_apply_offer_btn.pack(side="right", padx=(0, 8))
        self._maybe_disable(webrtc_apply_offer_btn, HAS_WEBRTC, "WebRTC removed in LAN build")

        self.prog_recv = ttk.Progressbar(self.recv_body, length=400, mode="determinate")
        self.prog_recv.pack(fill="x", pady=(8, 10))

    def _build_tab_merge(self):
        self.tab_merge = ttk.Frame(self.nb)
        self.nb.add(self.tab_merge, text="Merge")

        # ================= Databases =================
        dbgrp = ttk.LabelFrame(self.tab_merge, text="Databases")
        dbgrp.pack(fill="x", padx=6, pady=(10, 8))

        # Source
        row_src = ttk.Frame(dbgrp)
        row_src.pack(fill="x", pady=(4, 4))

        ttk.Label(row_src, text="Source DB:").pack(side="left")
        self.entry_merge_src = ttk.Entry(row_src, width=60)
        self.entry_merge_src.pack(side="left", padx=6)
        ttk.Button(row_src, text="Browse…", command=self._pick_merge_src).pack(side="left")

        # Destination
        row_dst = ttk.Frame(dbgrp)
        row_dst.pack(fill="x", pady=(4, 4))

        ttk.Label(row_dst, text="Destination DB:").pack(side="left")
        self.entry_merge_dst = ttk.Entry(row_dst, width=60)
        self.entry_merge_dst.pack(side="left", padx=6)
        ttk.Button(row_dst, text="Browse…", command=self._pick_merge_dst).pack(side="left")

        # ================= Options =================
        optgrp = ttk.LabelFrame(self.tab_merge, text="Options")
        optgrp.pack(fill="x", padx=6, pady=(6, 8))

        # делаем 2 столбца
        optgrp.columnconfigure(0, weight=1)
        optgrp.columnconfigure(1, weight=1)

        # Column 1
        col1 = ttk.Frame(optgrp)
        col1.grid(row=0, column=0, sticky="nw", padx=(4, 2), pady=(4, 4))

        self.merge_dry = tk.BooleanVar(value=False)
        ttk.Checkbutton(col1, text="Dry-run (read only)", variable=self.merge_dry).pack(anchor="w", pady=2)

        self.merge_skip_orphans = tk.BooleanVar(value=False)
        ttk.Checkbutton(col1, text="Skip orphans", variable=self.merge_skip_orphans).pack(anchor="w", pady=2)

        self.merge_verbose_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(col1, text="Verbose logs", variable=self.merge_verbose_log).pack(anchor="w", pady=2)

        # Column 2
        col2 = ttk.Frame(optgrp)
        col2.grid(row=0, column=1, sticky="nw", padx=(2, 4), pady=(4, 4))

        self.merge_skip_posters_without_hash = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            col2,
            text="Skip posters without hash",
            variable=self.merge_skip_posters_without_hash,
        ).pack(anchor="w", pady=2)

        self.merge_vacuum_optimize = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            col2,
            text="VACUUM/optimize after merge",
            variable=self.merge_vacuum_optimize,
        ).pack(anchor="w", pady=2)

        # ================= Action =================
        btn_row = ttk.Frame(self.tab_merge)
        btn_row.pack(fill="x", pady=(6, 4), padx=6)

        self.btn_merge = ttk.Button(btn_row, text="Merge", command=self._run_merge)
        self.btn_merge.pack(side="right")

        # Progress bar
        self.prog_merge = ttk.Progressbar(self.tab_merge, length=400, mode="indeterminate")
        self.prog_merge.pack(fill="x", padx=6, pady=(0, 10))

    def _build_tab_logs(self):
        self.tab_logs = ttk.Frame(self.nb)
        self.nb.add(self.tab_logs, text="Logs")
        wrap = ttk.Frame(self.tab_logs)
        wrap.pack(fill="both", expand=True)
        self.txt = tk.Text(wrap, height=14, wrap="word")
        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=yscroll.set)
        topbar = ttk.Frame(self.tab_logs); topbar.pack(fill="x", pady=(6,4))
        ttk.Button(topbar, text="Save log…", command=self._save_log).pack(side="left")
        ttk.Button(topbar, text="Clear log", command=self._clear_log).pack(side="left", padx=(6,0))
        self.txt.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    # ---------- Logs ----------
    def _log(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt.insert("end", f"[{ts}] {s}\n")
        self.txt.see("end")

    def _save_log(self):
        p = filedialog.asksaveasfilename(title="Save log", defaultextension=".txt",
                                         filetypes=[("Text files","*.txt"),("All files","*.*")])
        if not p:
            return
        try:
            data = self.txt.get("1.0", "end-1c")
            Path(p).write_text(data, encoding="utf-8")
            messagebox.showinfo("Logs", "Сохранено.", parent=self)
        except Exception as e:
            messagebox.showerror("Logs", f"Ошибка сохранения: {e}", parent=self)

    def _clear_log(self):
        try:
            self.txt.delete("1.0", "end")
        except Exception:
            pass

    # ---- Merge ----
    def _pick_merge_src(self):
        p = filedialog.askopenfilename(title="Select Source DB",
                                       filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")])
        if p: self.entry_merge_src.delete(0, "end"); self.entry_merge_src.insert(0, p)

    def _pick_merge_dst(self):
        p = filedialog.askopenfilename(title="Select Destination DB",
                                       filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")])
        if p: self.entry_merge_dst.delete(0, "end"); self.entry_merge_dst.insert(0, p)

    def _run_merge(self):
        src = self.entry_merge_src.get().strip()
        dst = self.entry_merge_dst.get().strip()
        dry = self.merge_dry.get()
        skip_posters_without_hash = self.merge_skip_posters_without_hash.get()
        skip_orphans = self.merge_skip_orphans.get()
        vacuum_optimize = self.merge_vacuum_optimize.get()
        verbose = self.merge_verbose_log.get()
        if self.merge_running:
            messagebox.showwarning("Merge", "Merge уже выполняется, дождись завершения.", parent=self)
            return
        if not src or not dst:
            messagebox.showerror("Merge", "Укажи обе БД: Source и Destination.", parent=self)
            return
        if src == dst:
            messagebox.showerror("Merge", "Source и Destination не должны совпадать.", parent=self)
            return

        self._log(f"Merge: {src} → {dst}  (dry_run={dry}) (verbose={verbose})")
        self.nb.select(self.tab_merge)
        self.prog_merge.start(60)
        self.merge_events = {"cnt": 0}
        self.merge_running = True
        if hasattr(self, "btn_merge"):
            self.btn_merge.config(state="disabled")

        def on_event(table, op):
            self.after(0, lambda: self._log(f"[merge] {table}: {op}"))

        def worker():
            try:
                if skip_posters_without_hash: self._log(
                    "NOTE: skip_posters_without_hash — пропускать постеры без hash.")
                if skip_orphans: self._log("NOTE: skip_orphans — пропускать без родителя...")
                if vacuum_optimize: self._log("NOTE: vacuum_optimize — оптимизировать после слияния...")

                if dry: self._log("NOTE: dry-run — изменения не записаны.")
                if verbose: self._log("NOTE: verbose logs enabled.")
                stats, viol, orphans = run_merge(
                    src,
                    dst,
                    skip_posters_without_hash=skip_posters_without_hash,
                    skip_orphans=skip_orphans,
                    vacuum_optimize=vacuum_optimize,
                    dry_run=dry,
                    on_event=on_event,
                    verbose=verbose,
                )

                def done():
                    self.prog_merge.stop()
                    self.merge_running = False
                    if hasattr(self, "btn_merge"):
                        self.btn_merge.config(state="normal")
                    messagebox.showinfo("Merge", "Merge process: Done.", parent=self)

                    if viol:
                        self._log("\n=== VIOLATION SUMMARY (source → dest) ===")
                        head = [tuple(v) for v in viol[:10]]
                        self._log(f"{len(viol)} violations, first 10:\n{head}")
                    else:
                        self._log("\n=== VIOLATION SUMMARY (source → dest) ===")
                        self._log("0 violations")

                    self._log("=== MERGE SUMMARY (source → dest) ===")
                    for t, s in stats.items():
                        self._log(
                            f"{t:22s}  inserted:{s['insert']:6d}  updated:{s['update']:6d}  skipped:{s['skip']:6d}")

                    if orphans:
                        try:
                            dst_dir = os.path.dirname(dst) or "."
                            csv_path = os.path.join(dst_dir, "merge_orphans.csv")
                            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                                w = csv.writer(f, delimiter=";")
                                w.writerow(["table", "op", "key"])
                                for o in orphans:
                                    w.writerow([o.get("table"), o.get("op"), o.get("key")])
                            self._log(f"Orphans CSV saved: {csv_path} ({len(orphans)} rows)")
                        except Exception as e:
                            self._log(f"Failed to save orphans CSV: {e}")

                self.after(0, done)
            except Exception as e:
                msg = str(e)
                tb = traceback.format_exc()

                def handler(m=msg, tb_text=tb):
                    self.prog_merge.stop()
                    self.merge_running = False
                    if hasattr(self, "btn_merge"):
                        self.btn_merge.config(state="normal")
                    self._log("Merge error: " + m)
                    self._log("Traceback:\n" + tb_text)
                    messagebox.showerror("Merge", m, parent=self)

                self.after(0, handler)
        threading.Thread(target=worker, daemon=True).start()

    # ---- Utils ----
    def _maybe_disable(self, widget, feature_flag: bool, msg: str):
        if not feature_flag:
            widget.config(state="disabled")
            widget._disabled_reason = msg

    def _make_collapsible(self, labelframe: ttk.LabelFrame) -> None:
        """
        Делает ttk.LabelFrame сворачиваемым.
        Внутренние виджеты будут скрываться / показываться.
        """

        # Создаём контейнер для содержимого
        content = ttk.Frame(labelframe)
        # Переносим детей labelFrame внутрь content
        for child in list(labelframe.winfo_children()):
            if isinstance(child, ttk.Label):
                # пропускаем сам заголовок
                continue
            child.pack_forget()
            child.master = content
            child.pack(fill="x", padx=4, pady=2)

        # Кнопка в заголовке
        btn = ttk.Label(labelframe, text="▼", cursor="hand2")
        btn.place(relx=1.0, x=-20, y=0, anchor="ne")

        def toggle():
            if content.winfo_ismapped():
                content.pack_forget()
                btn.config(text="►")
            else:
                content.pack(fill="x", padx=4, pady=(2, 4))
                btn.config(text="▼")

        btn.bind("<Button-1>", lambda e: toggle())

        # Первоначальное раскрытие
        content.pack(fill="x", padx=4, pady=(2, 4))

    def _paste_text(self, text_widget: tk.Text) -> None:
        """
        Вставить текст из буфера обмена в указанный Text:
        - читает clipboard
        - триммит
        - заменяет содержимое виджета
        """
        try:
            data = self.clipboard_get()
        except Exception as e:
            self._log(f"[webrtc] clipboard read error: {e}")
            return

        data = (data or "").strip()
        if not data:
            self._log("[webrtc] clipboard is empty")
            return

        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", data)
        self._log("[webrtc] text pasted from clipboard")

    def _copy_text(self, text_widget: tk.Text) -> None:
        data = text_widget.get("1.0", "end").strip()
        if not data:
            self._log("[webrtc] nothing to copy")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(data)
            self._log("[webrtc] text copied to clipboard")
        except Exception as e:
            self._log(f"[webrtc] clipboard error: {e}")

    def _clear_text(self, text_widget: tk.Text) -> None:
        text_widget.delete("1.0", "end")
        self._log("[webrtc] text cleared")

    def _make_scrollable(self, parent: tk.Widget) -> ttk.Frame:
        """
        Создаёт внутри parent прокручиваемую область:
          parent
            ├─ Canvas + вертикальный Scrollbar
            └─ внутри Canvas — Frame, в который уже пакуются все остальные виджеты.
        Возвращает этот внутренний Frame.
        """
        # Canvas + scrollbar
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Внутренний фрейм, который будет реальным контейнером
        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Обновляем scrollregion при изменении размера inner
        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_frame_configure)

        # Обновляем ширину inner при изменении размера canvas (чтобы не было полосы справа)
        def _on_canvas_configure(event):
            canvas.itemconfig(inner_id, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        # Прокрутка колёсиком мыши
        def _on_mousewheel(event):
            # Windows / Linux
            delta = -1 * (event.delta // 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, "units")

        # Для Windows/Unix
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)
        # Для X11, если вдруг понадобится:
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        inner.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        inner.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        return inner

    def _on_progress_send(self, done: int, total: int):
        def upd():
            self._set_progress(self.prog_send, done, total)
            if total and done >= total:
                self.after(400, lambda: self._set_progress(self.prog_send, 0, total))
                self.send_sas_code.set("—")
                self.send_sas_fp.set("—")

        self.after(0, upd)

    def _on_progress_recv(self, done: int, total: int):
        def upd():
            self._set_progress(self.prog_recv, done, total)
            if total and done >= total:
                self.after(800, lambda: self._set_progress(self.prog_recv, 0, total))
                self.recv_sas_code.set("—")
                self.recv_sas_fp.set("—")

        self.after(0, upd)

    @staticmethod
    def _set_progress(widget: ttk.Progressbar, done: int, total: int):
        if total and total > 0:
            widget['maximum'] = total
            widget['value'] = min(done, total)

    def _set_recv_led(self, running: bool):
        # green (#5cb85c) / red (#d9534f)
        if not hasattr(self, "recv_led"):
            return
        fill = "#5cb85c" if running else "#d9534f"
        outline = "#3d8b3d" if running else "#a94442"
        try:
            self.recv_led.itemconfig(self._recv_led_id, fill=fill, outline=outline)
        except Exception:
            pass

    def _on_internet_info(self, ext_ip: str | None, nat_type: str, upnp_status: str):
        def upd():
            self.internet_ext_ip.set(ext_ip or "—")
            self.internet_nat_type.set(nat_type or "—")
            self.internet_upnp_status.set(upnp_status or "—")
        self.after(0, upd)

    def _on_check_internet_port(self):
        """
        Проверка доступности внешнего IP:port.
        Работает только если:
          - есть external IP
          - приёмник запущен
        На самом деле это попытка подключиться с этой же машины
        (если роутер не поддерживает hairpin NAT, может не сработать даже при корректном пробросе).
        """
        host = self.internet_ext_ip.get().strip()
        if not host or host == "—":
            messagebox.showwarning(
                "Internet check",
                "Нет внешнего IP. Сначала запусти приёмник в режиме Internet (TCP).",
                parent=self,
            )
            return

        try:
            port = int(self.entry_port_recv.get().strip() or "8765")
        except ValueError:
            messagebox.showerror("Error", "Incorrect port", parent=self)
            return

        self._log(f"Internet check: trying {host}:{port} …")

        async def probe():
            import asyncio
            try:
                rdr, wtr = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=2.0,
                )
                wtr.close()
                await wtr.wait_closed()
                return True
            except Exception:
                return False

        fut = self.asyncio_thread.call(probe())

        def done_cb(_):
            ok = False
            try:
                ok = fut.result(timeout=0)
            except Exception:
                ok = False

            if ok:
                self._log("Internet check: OK — external port reachable.")
                messagebox.showinfo(
                    "Internet check",
                    "OK — внешний порт доступен (с текущей машины).\n"
                    "Учти, что это всё равно не гарантирует доступность из любой сети.",
                    parent=self,
                )
            else:
                self._log("Internet check: failed — no connectivity.")
                messagebox.showwarning(
                    "Internet check",
                    "Подключиться к внешнему IP не удалось.\n\n"
                    "Возможные причины:\n"
                    "  • Приёмник не запущен\n"
                    "  • UPnP не сработал или отключён\n"
                    "  • Маршрутизатор не поддерживает hairpin NAT\n"
                    "  • Провайдер или фаервол блокирует соединение",
                    parent=self,
                )

        fut.add_done_callback(done_cb)

    def _on_webrtc_message(self, data: bytes):
        """
        Обработчик сообщений по WebRTC DataChannel (receiver side).

        Протокол:
          1) первое сообщение — JSON header {"kind":"header","name":"...","size":...}
          2) далее — сырые чанки байт файла
        """
        import json, os
        from pathlib import Path

        # 1) Если метаданных ещё нет — ожидаем header
        if self.webrtc_rx_meta is None:
            try:
                text = data.decode("utf-8")
                obj = json.loads(text)
            except Exception:
                self._log("[webrtc] first message is not valid JSON header; ignoring")
                return

            if obj.get("kind") != "header":
                self._log(f"[webrtc] unexpected JSON message (no kind=header): {obj}")
                return

            name = obj.get("name") or "webrtc_incoming.db"
            size = int(obj.get("size") or 0)

            incoming_dir = Path("./incoming")
            incoming_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = incoming_dir / f"{name}.tmp"

            try:
                f = open(tmp_path, "wb")
            except Exception as e:
                self._log(f"[webrtc] cannot open file for write: {e}")
                return

            self.webrtc_rx_meta = {
                "name": name,
                "size": size,
                "tmp_path": tmp_path,
            }
            self.webrtc_rx_file = f
            self.webrtc_rx_received = 0

            self._log(f"[webrtc] header received: {name} ({size} bytes)")
            # подготовим прогрессбар
            self.after(0, lambda: self._set_progress(self.prog_recv, 0, size))
            return

        # 2) Метаданные уже есть — это должен быть чанк байт
        if self.webrtc_rx_file is None:
            self._log("[webrtc] got data chunk but file handle is None; ignoring")
            return

        try:
            self.webrtc_rx_file.write(data)
            self.webrtc_rx_received += len(data)
        except Exception as e:
            self._log(f"[webrtc] write error: {e}")
            try:
                self.webrtc_rx_file.close()
            except Exception:
                pass
            self.webrtc_rx_file = None
            return

        meta = self.webrtc_rx_meta or {}
        total = int(meta.get("size") or 0)
        done = self.webrtc_rx_received

        # обновляем прогрессбар в GUI-потоке
        self.after(0, lambda: self._on_progress_recv(done, total))

        # 3) Проверяем завершение по размеру
        if total and done >= total:
            try:
                self.webrtc_rx_file.close()
            except Exception:
                pass
            self.webrtc_rx_file = None

            tmp_path = meta.get("tmp_path")
            name = meta.get("name") or "webrtc_incoming.db"
            incoming_dir = os.path.dirname(str(tmp_path)) if tmp_path else "./incoming"
            final_path = os.path.join(incoming_dir, name)

            try:
                if tmp_path:
                    os.replace(tmp_path, final_path)
                self._log(f"[webrtc] file received and saved: {final_path}")
                # выносим диалог и финальный прогресс в GUI-поток
                self.after(0, lambda: self._on_receive_done(final_path))
            except Exception as e:
                self._log(f"[webrtc] finalize error: {e}")

            # сбрасываем состояние
            self.webrtc_rx_meta = None
            self.webrtc_rx_file = None
            self.webrtc_rx_received = 0

    def _webrtc_apply_offer(self):
        offer = self.webrtc_offer_recv.get("1.0", "end").strip()
        if not offer:
            messagebox.showerror("WebRTC", "Вставь Offer от отправителя.", parent=self)
            return

        # сброс состояния приёмника WebRTC
        if self.webrtc_rx_file:
            try:
                self.webrtc_rx_file.close()
            except Exception:
                pass
        self.webrtc_rx_meta = None
        self.webrtc_rx_file = None
        self.webrtc_rx_received = 0

        # лениво создаём core
        if not self.webrtc_rx_core:
            self.webrtc_rx_core = WebRTCReceiverCore(log=self._log)
            self.webrtc_rx_core.set_on_message(self._on_webrtc_message)

        self.webrtc_ice_status.set("processing offer…")
        self._log("[webrtc] applying offer on receiver, creating answer…")

        async def worker():
            try:
                answer = await self.webrtc_rx_core.accept_offer_and_create_answer(offer)

                def upd_answer():
                    self.webrtc_answer_recv.delete("1.0", "end")
                    self.webrtc_answer_recv.insert("1.0", answer)
                    self.webrtc_ice_status.set("waiting ICE…")
                    self._log("[webrtc] Answer created, скопируй его отправителю")

                self.after(0, upd_answer)

                # ждём соединения
                await self.webrtc_rx_core.wait_connected()

                def upd_ok():
                    self.webrtc_ice_status.set("connected")
                    self._log("[webrtc] WebRTC connected (receiver side)")

                self.after(0, upd_ok)

            except WebRTCSignalingError as e:
                self._log(f"[webrtc] signaling error: {e}")
                def show_err(msg=str(e)):
                    self.webrtc_ice_status.set("error")
                    messagebox.showerror("WebRTC", f"Signaling error: {msg}", parent=self)

                self.after(0, show_err)
            except Exception as e:
                self._log(f"[webrtc] unexpected error: {e}")
                def show_err(msg=str(e)):
                    self.webrtc_ice_status.set("error")
                    messagebox.showerror("WebRTC", f"Error: {msg}", parent=self)

                self.after(0, show_err)

        self.asyncio_thread.call(worker())

    def _on_webrtc_use_answer(self):
        """
        Пользователь нажал кнопку "Use Answer / connect" на вкладке Send:
        - читаем текст из поля Answer,
        - если пусто — ругаемся,
        - если ок — сохраняем строку и ставим Event,
          чтобы фоновый WebRTC-отправитель продолжил handshake.
        """
        text = self.webrtc_answer.get("1.0", "end").strip()
        if not text:
            messagebox.showerror(
                "WebRTC",
                "Вставь Answer от приёмника в поле ниже перед тем, как продолжать.",
                parent=self,
            )
            return

        self._webrtc_answer_value = text
        self._webrtc_answer_event.set()
        self._log("[webrtc] Answer принят, продолжаю подключение…")

    def _update_human(self, entry: tk.Entry, var: tk.StringVar, kind: str):
        txt = entry.get().strip()
        if not txt:
            var.set("")
            return
        try:
            val = float(txt.replace(",", "."))
        except ValueError:
            var.set("")
            return

        if kind == "chunk":
            mib = val
            bytes_ = int(mib * 1024 * 1024)
            var.set(f"≈ {mib:.2f} MiB ({bytes_:,} bytes)")
        elif kind == "speed":
            mbps = val / 1024.0
            var.set(f"≈ {mbps:.2f} MiB/s")

    def _delete_snapshot(self):
        from pathlib import Path
        snap = Path("db_snapshot.sqlite")
        if not snap.exists():
            messagebox.showinfo("Snapshot", "Снапшот не найден (db_snapshot.sqlite).", parent=self)
            self._log("Snapshot: db_snapshot.sqlite not found")
            return
        try:
            snap.unlink()
            messagebox.showinfo("Snapshot", "Снапшот удалён (db_snapshot.sqlite).", parent=self)
            self._log("Snapshot: db_snapshot.sqlite deleted")
        except Exception as e:
            messagebox.showerror("Snapshot", f"Не удалось удалить снапшот: {e}", parent=self)
            self._log(f"Snapshot: error deleting db_snapshot.sqlite: {e}")

    def _start_mdns_browse(self):
        if self._zc:
            try:
                self._zc.close()
            except Exception:
                pass
            self._zc = None
        self._mdns_hosts.clear()
        try:
            self._zc = Zeroconf()
            self._mdns_browser = ServiceBrowser(self._zc, MDNS_SERVICE_TYPE, handlers=[self._on_mdns_service])
            self.mdns_status.set("mDNS: scanning…")
            self._log("mDNS: searching receiver…")
            self.after(3000, self._finish_mdns_scan)
        except Exception as e:
            self.mdns_status.set("mDNS: error")
            self._log(f"mDNS error: {e}")

    def _on_mdns_service(self, zeroconf, service_type, name, state_change):
        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return
            try:
                for addr in info.addresses:
                    ip = socket.inet_ntoa(addr)
                    host = f"{ip}"
                    self._mdns_hosts.add(host)
            except Exception:
                pass

    def _finish_mdns_scan(self):
        items = list(self._mdns_hosts)
        items.sort()
        if items:
            self.cmb_host["values"] = items + list(self.cfg.get("recent", []))
            first = items[0]
            if ":" in first:
                ip, p = first.split(":")
                self.cmb_host.set(ip)
                self.entry_port_send.delete(0, "end")
                self.entry_port_send.insert(0, p)
            self.mdns_status.set(f"mDNS: found {len(items)}")
            self._log(f"mDNS: find {len(items)} receivers")
        else:
            self.mdns_status.set("mDNS: none")
            self._log("mDNS: receiver was not found")

    def _clear_mdns(self):
        self._mdns_hosts.clear()
        self.cmb_host["values"] = self.cfg.get("recent", [])
        self.mdns_status.set("mDNS: cleared")

    def _on_check_conn(self):
        host = self.cmb_host.get().strip()
        try:
            port = int(self.entry_port_send.get().strip() or "8765")
        except ValueError:
            messagebox.showerror("Error", "Incorrect port", parent=self)
            return

        self._log(f"Check connection: {host}:{port} …")

        async def probe():
            try:
                rdr, wtr = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
                wtr.close()
                await wtr.wait_closed()
                return True
            except Exception:
                return False

        fut = self.asyncio_thread.call(probe())

        def done_cb(_):
            ok = False
            try:
                ok = fut.result(timeout=0)
            except Exception:
                ok = False
            self._log("Проверка: OK" if ok else "Проверка: нет соединения")

            if ok:
                messagebox.showinfo("Проверка соединения", "OK — порт доступен.", parent=self)
            else:
                msg = (
                    "Соединение не установлено.\n\n"
                    "Возможные причины:\n"
                    "  • Приёмник не запущен на целевой машине\n"
                    "  • Блокирует Windows Firewall или другой фаервол\n\n"
                    "Для Windows вы можете открыть порт вручную (от Администратора):\n"
                    f'  netsh advfirewall firewall add rule name="PlayerDBSync_{port}" '
                    f'dir=in action=allow protocol=TCP localport={port}\n'
                )
                messagebox.showwarning("Проверка соединения", msg, parent=self)
                self._log(
                    "Firewall hint (Windows): run as Administrator:\n"
                    f'  netsh advfirewall firewall add rule name="PlayerDBSync_{port}" '
                    f'dir=in action=allow protocol=TCP localport={port}'
                )

        fut.add_done_callback(done_cb)

    # ---------- SEND ----------
    def _on_send(self):
        host = self.cmb_host.get().strip()
        if not host:
            messagebox.showerror("Ошибка", "Укажите адрес получателя", parent=self)
            return
        try:
            port = int(self.entry_port_send.get().strip() or "8765")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректный порт", parent=self)
            return

        path = filedialog.askopenfilename(
            title="Выберите SQLite БД",
            filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")]
        )
        if not path:
            return

        transport_mode = getattr(self, "var_transport_send", None)
        mode = transport_mode.get() if transport_mode is not None else "tcp"

        self._log(f"Отправка файла: {path} → {host}:{port}")
        self.nb.select(self.tab_send)

        def sas_info_cb(sas: str, fp: str):
            def upd():
                self.send_sas_code.set(sas)
                self.send_sas_fp.set(fp)
                self._log(f"SAS (sender): {sas} | FP: {fp}")
                self.nb.select(self.tab_send)
            self.after(0, upd)

        try:
            chunk_mib = float(self.entry_chunk.get().strip() or "0")
            if chunk_mib <= 0:
                raise ValueError
            chunk_size = int(chunk_mib * 1024 * 1024)
        except ValueError:
            messagebox.showerror("Ошибка", "Chunk size должен быть положительным числом (MiB).", parent=self)
            return
        try:
            speed_kbps = self.entry_speed.get().strip()
            speed_kbps = int(speed_kbps) if speed_kbps else None
            if speed_kbps is not None and speed_kbps <= 0:
                speed_kbps = None
        except ValueError:
            messagebox.showerror("Ошибка", "Speed limit должен быть целым числом (KB/s) или пусто.", parent=self)
            return

        use_gzip = self.var_send_compress.get()
        vacuum_snapshot = self.var_send_vacuum.get()

        # --- Выбор транспорта ---
        if mode == "tcp":
            if HAS_STUN and TcpSenderTransport is not None:
                self._log("[tcp] Using Internet-capable TCP transport")
                transport = TcpSenderTransport(
                    host=host,
                    port=port,
                    chunk_size=chunk_size,
                    speed_kbps=speed_kbps,
                    log=self._log,
                    on_progress=self._on_progress_send,
                    sas_info=sas_info_cb,
                    use_gzip=use_gzip,
                    vacuum_snapshot=vacuum_snapshot,
                )
            else:
                self._log("[tcp] Using LAN TCP transport (no STUN/UPnP in this build)")
                transport = TcpSenderTransportLan(
                    host=host,
                    port=port,
                    chunk_size=chunk_size,
                    speed_kbps=speed_kbps,
                    log=self._log,
                    on_progress=self._on_progress_send,
                    sas_info=sas_info_cb,
                    use_gzip=use_gzip,
                    vacuum_snapshot=vacuum_snapshot,
                )
        elif mode == "webrtc":
            def show_offer(sdp: str) -> None:
                def upd():
                    self.webrtc_offer.delete("1.0", "end")
                    self.webrtc_offer.insert("1.0", sdp)
                    self._log(
                        "[webrtc] Offer создан. "
                        "Скопируй его на приёмник, там нажми 'Apply offer / create answer', "
                        "затем вставь Answer сюда и нажми 'Use Answer / connect'."
                    )
                self.after(0, upd)

            def wait_for_answer() -> str:
                # готовим состояние перед началом ожидания
                self._webrtc_answer_value = ""
                self._webrtc_answer_event.clear()
                self._log("[webrtc] Ожидаю Answer — вставь его в поле и нажми 'Use Answer / connect'.")

                # Блокирующее ожидание в рабочем потоке (НЕ в Tk!)
                self._webrtc_answer_event.wait()
                ans = self._webrtc_answer_value.strip()
                return ans

            if not HAS_WEBRTC or WebRTCSenderTransport is None:
                self._log("[webrtc] not available in this build")
                messagebox.showerror("WebRTC", "WebRTC is not available in this build.")
                return
            else:
                transport = WebRTCSenderTransport(
                    log=self._log,
                    on_progress=self._on_progress_send,
                    show_offer=show_offer,
                    wait_for_answer=wait_for_answer,
                    chunk_size=chunk_size,
                )

        else:
            messagebox.showerror("Ошибка", f"Неизвестный режим транспорта: {mode}", parent=self)
            return

        async def _runner():
            try:
                await transport.send_db(path)
            finally:
                try:
                    await transport.close()
                except Exception:
                    pass

        fut = self.asyncio_thread.call(_runner())
        self._pending.append(fut)

        def done_cb(_):
            try:
                self._pending.remove(fut)
            except ValueError:
                pass
            err = fut.exception()
            if err:
                self._log(f"Ошибка отправки ({mode}): {err}")
                messagebox.showerror("Ошибка", str(err), parent=self)
            else:
                self._log(f"Отправка завершена ({mode})")
                addr = f"{host}"
                recent = [addr] + [x for x in self.cfg.get("recent", []) if x != addr]
                self.cfg["recent"] = recent[:8]
                self.cfg["last_port"] = str(port)
                self.cfg["chunk_size"] = self.entry_chunk.get().strip()
                self.cfg["speed_kbps"] = "" if speed_kbps is None else str(speed_kbps)
                self.cfg["compress_gzip"] = "1" if self.var_send_compress.get() else "0"
                self.cfg["sender_vacuum"] = "1" if self.var_send_vacuum.get() else "0"
                save_gui_cfg(self.cfg)
                self.cmb_host["values"] = self.cfg["recent"]
        fut.add_done_callback(done_cb)

    # ---------- RECEIVE ----------
    def _on_toggle_receive(self):
        transport = getattr(self, "var_transport_recv", None)
        transport_mode = transport.get() if transport is not None else "tcp"

        if not self.receiver_running:
            # --- START ---
            try:
                port = int(self.entry_port_recv.get().strip() or "8765")
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректный порт", parent=self)
                return

            if transport_mode == "tcp":
                tcp_mode = getattr(self, "var_tcp_mode_recv", None)
                tcp_mode_val = tcp_mode.get() if tcp_mode is not None else "lan"

                if tcp_mode_val == "lan":
                    # Обычный DBReceiver, как раньше
                    self.receiver_mode = "lan"
                    self.receiver_tcp = DBReceiver(
                        host="0.0.0.0",
                        port=port,
                        chunk_dir="./incoming",
                        on_progress=self._on_progress_recv,
                        sas_confirm=self._sas_confirm_inline,
                        on_done=self._on_receive_done,
                        log=self._log,
                    )
                    self._log(f"Запуск приёмника (LAN) на порту {port} …")
                    self.recv_status.set(f"Server: Running (LAN) on 0.0.0.0:{port}")
                    self.receiver_running = True
                    self._set_recv_led(True)
                    self.asyncio_thread.call(self.receiver_tcp.start_listen())

                else:  # internet
                    self.receiver_mode = "internet"
                    self.receiver_inet = InternetReceiver(
                        port=port,
                        chunk_dir="./incoming",
                        on_progress=self._on_progress_recv,
                        sas_confirm=self._sas_confirm_inline,
                        on_done=self._on_receive_done,
                        log=self._log,
                        info_cb=self._on_internet_info,
                    )
                    self._log(f"Запуск приёмника (Internet TCP) на порту {port} …")
                    self.recv_status.set(f"Server: Running (Internet) on 0.0.0.0:{port}")
                    self.receiver_running = True
                    self._set_recv_led(True)
                    self.asyncio_thread.call(self.receiver_inet.start())

            elif transport_mode == "webrtc":

                if not HAS_WEBRTC:
                    self._log("[webrtc] not available in this build")
                    messagebox.showerror("WebRTC", "WebRTC is not available in this build.")
                    return

                self.receiver_mode = "webrtc"
                self.receiver_running = True
                self._set_recv_led(True)
                self.recv_status.set("Server: WebRTC (waiting for Offer)")
                self._log("WebRTC receive: вставь Offer и нажми 'Apply offer / create answer'.")
            else:
                messagebox.showerror("Receive", f"Неизвестный режим транспорта: {transport_mode}", parent=self)
                return
        else:
            # --- STOP ---
            self._log("Остановка приёмника …")
            self.recv_status.set("Server: Stopped")
            self.receiver_running = False
            self._set_recv_led(False)

            if self.receiver_mode == "lan" and self.receiver_tcp:
                self.asyncio_thread.call(self.receiver_tcp.stop())
            elif self.receiver_mode == "internet" and self.receiver_inet:
                self.asyncio_thread.call(self.receiver_inet.stop())
            elif self.receiver_mode == "webrtc" and self.webrtc_rx_core:
                self.asyncio_thread.call(self.webrtc_rx_core.close())

            self.receiver_tcp = None
            self.receiver_inet = None
            self.receiver_mode = "lan"
            self.webrtc_ice_status.set("idle")

    def _reset_tofu(self):
        try:
            if TOFU_FILE.exists():
                save_tofu({})
            messagebox.showinfo("TOFU", "Хранилище доверия очищено.", parent=self)
            self._log("TOFU: cleared (~/.player_db_trust.json)")
        except Exception as e:
            messagebox.showerror("TOFU", f"Не удалось очистить: {e}", parent=self)

    def _sas_confirm_inline(self, sas_code: str, fp: str) -> bool:
        self.after(0, lambda: (
            self.recv_sas_code.set(sas_code),
            self.recv_sas_fp.set(fp),
            self.nb.select(self.tab_recv)
        ))
        ev = threading.Event()
        holder = {"ok": False, "ev": ev}
        self._sas_event = holder
        ev.wait()
        self._sas_event = None
        return holder["ok"]

    def _sas_accept(self):
        if self._sas_event:
            self._log("SAS: Accept clicked")
            self._sas_event["ok"] = True
            self._sas_event["ev"].set()

    def _sas_reject(self):
        if self._sas_event:
            self._log("SAS: Cancel clicked")
            self._sas_event["ok"] = False
            self._sas_event["ev"].set()

    def _on_receive_done(self, path: str):
        self.after(0, lambda: (
            self._log(f"Файл сохранён: {path}"),
            messagebox.showinfo("Receive", f"Файл сохранён:\n{path}", parent=self)
        ))

    # ---------- shutdown ----------
    def on_close(self):
        try:
            # 1) Если ждём SAS — принудительно "отклоняем" и будим поток
            if getattr(self, "_sas_event", None):
                self._log("SAS: window closed, cancelling SAS")
                try:
                    self._sas_event["ok"] = False
                    self._sas_event["ev"].set()
                except Exception:
                    pass
                self._sas_event = None

            # 2) Останавливаем приёмник
            if self.receiver_running:
                if self.receiver_mode == "lan" and self.receiver_tcp:
                    self.asyncio_thread.call(self.receiver_tcp.stop())
                elif self.receiver_mode == "internet" and self.receiver_inet:
                    self.asyncio_thread.call(self.receiver_inet.stop())

            # 3) Ждём незавершённые future'ы (отправка и т.п.)
            for fut in list(self._pending):
                try:
                    fut.result(timeout=2)
                except Exception:
                    pass

            # 4) Закрываем Zeroconf
            try:
                if self._zc:
                    self._zc.close()
            except Exception:
                pass
        finally:
            self.asyncio_thread.stop()
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
