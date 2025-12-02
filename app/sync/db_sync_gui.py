# db_sync_gui.py
import os
import csv
import json
import socket
import asyncio
import threading
import traceback
import tkinter as tk

from pathlib import Path
from typing import Optional
from datetime import datetime
from tkinter import ttk, filedialog, messagebox

os.environ.setdefault("ZC_DISABLE_CYTHON", "1")
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

from db_merge import run_merge
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
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Player DB Sync (LAN)")
        self.geometry("780x450")
        self['padx'] = 8
        self['pady'] = 8
        self._zc = None
        self._mdns_browser = None
        self._mdns_hosts = set()
        self.asyncio_thread = AsyncioThread()
        self.receiver: Optional[DBReceiver] = None
        self.receiver_running = False
        self.merge_running = False
        self._pending = []
        self._sas_event = None
        self.cfg = load_gui_cfg()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self._build_tab_send()
        self._build_tab_receive()
        self._build_tab_merge()
        self._build_tab_logs()

        self._log("Готово. Используйте вкладки Send/Receive. История адресов сохраняется в ~/.player_db_gui.json.")

    # ---------- Tabs ----------

    def _build_tab_send(self):
        self.tab_send = ttk.Frame(self.nb)
        self.nb.add(self.tab_send, text="Send")
        top = ttk.Frame(self.tab_send)
        top.pack(fill="x", pady=(10, 8))
        ttk.Label(top, text="Receiver:").pack(side="left")
        self.cmb_host = ttk.Combobox(top, width=28, values=self.cfg.get("recent", []))
        self.cmb_host.pack(side="left", padx=(6, 10))
        self.cmb_host.set(self.cfg["recent"][0] if self.cfg.get("recent") else "192.168.0.50")
        ttk.Label(top, text="Port:").pack(side="left")
        self.entry_port_send = ttk.Entry(top, width=7)
        self.entry_port_send.pack(side="left", padx=(6, 10))
        self.entry_port_send.insert(0, self.cfg.get("last_port", "8765"))
        btns = ttk.Frame(self.tab_send)
        btns.pack(fill="x", pady=(0, 8))
        ttk.Button(btns, text="Send DB…", command=self._on_send).pack(side="right", padx=6)
        ttk.Button(btns, text="Check connection", command=self._on_check_conn).pack(side="right")
        md = ttk.Frame(self.tab_send)
        md.pack(fill="x", pady=(0, 6))
        ttk.Button(md, text="Find active on LAN (mDNS)", command=self._start_mdns_browse).pack(side="left")
        ttk.Button(md, text="Clear list", command=self._clear_mdns).pack(side="left", padx=(6, 0))
        self.mdns_status = tk.StringVar(value="mDNS: idle")
        ttk.Label(md, textvariable=self.mdns_status).pack(side="left", padx=10)

        # Settings
        setgrp = ttk.LabelFrame(self.tab_send, text="Settings")
        setgrp.pack(fill="x", pady=(6, 6))
        srow = ttk.Frame(setgrp); srow.pack(fill="x", pady=(6, 2))
        ttk.Label(srow, text="Chunk size (bytes):").pack(side="left")
        self.entry_chunk = ttk.Entry(srow, width=6)
        self.entry_chunk.pack(side="left", padx=(6, 16))
        self.entry_chunk.insert(0, self.cfg.get("chunk_size", "2"))

        self.chunk_human = tk.StringVar()
        lbl_chunk_human = ttk.Label(srow, textvariable=self.chunk_human)
        lbl_chunk_human.pack(side="left", padx=(6, 0))

        srow2 = ttk.Frame(setgrp); srow2.pack(fill="x", pady=(6, 2))
        ttk.Label(srow2, text="Speed limit (KB/s):").pack(side="left")
        self.entry_speed = ttk.Entry(srow2, width=10)
        self.entry_speed.pack(side="left", padx=(6, 0))
        self.entry_speed.insert(0, self.cfg.get("speed_kbps", ""))

        self.speed_human = tk.StringVar()
        lbl_speed_human = ttk.Label(srow2, textvariable=self.speed_human)
        lbl_speed_human.pack(side="left", padx=(6, 0))

        self.var_send_compress = tk.BooleanVar(value=self.cfg.get("compress_gzip", False))
        ttk.Checkbutton(
            setgrp,
            text="Compress snapshot (gzip)",
            variable=self.var_send_compress
        ).pack(anchor="w", pady=(2, 2))

        self.var_send_vacuum = tk.BooleanVar(value=self.cfg.get("sender_vacuum", False))
        ttk.Checkbutton(
            setgrp,
            text="VACUUM snapshot before send",
            variable=self.var_send_vacuum
        ).pack(anchor="w", pady=(0, 2))


        def _update_human(entry: tk.Entry, var: tk.StringVar, kind: str):
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
                # MiB -> bytes
                mib = val
                bytes_ = int(mib * 1024 * 1024)
                var.set(f"≈ {mib:.2f} MiB ({bytes_:,} bytes)")
            elif kind == "speed":
                # KB/s -> MiB/s
                mbps = val / 1024.0
                var.set(f"≈ {mbps:.2f} MiB/s")

        self.entry_chunk.bind(
            "<KeyRelease>",
            lambda e: _update_human(self.entry_chunk, self.chunk_human, "chunk")
        )
        self.entry_speed.bind(
            "<KeyRelease>",
            lambda e: _update_human(self.entry_speed, self.speed_human, "speed")
        )

        self.after(100, lambda: _update_human(self.entry_chunk, self.chunk_human, "chunk"))
        self.after(100, lambda: _update_human(self.entry_speed, self.speed_human, "speed"))

        # ---- Snapshot management ----
        srow3 = ttk.Frame(setgrp); srow3.pack(fill="x", pady=(8, 2))
        ttk.Button(srow3, text="Delete snapshot", command=self._delete_snapshot).pack(side="left")

        sasgrp = ttk.LabelFrame(self.tab_send, text="SAS (sender)")
        sasgrp.pack(fill="x", pady=(6, 6))
        row1 = ttk.Frame(sasgrp); row1.pack(fill="x", pady=(6, 2))
        ttk.Label(row1, text="SAS:").pack(side="left")
        self.send_sas_code = tk.StringVar(value="—")
        ttk.Label(row1, textvariable=self.send_sas_code, font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=6)
        row2 = ttk.Frame(sasgrp)
        row2.pack(fill="x", pady=(2, 8))
        ttk.Label(row2, text="FP:").pack(side="left")
        self.send_sas_fp = tk.StringVar(value="—")
        ttk.Label(row2, textvariable=self.send_sas_fp).pack(side="left", padx=6)
        self.prog_send = ttk.Progressbar(self.tab_send, length=400, mode="determinate")
        self.prog_send.pack(fill="x", pady=(10, 10))

    def _build_tab_receive(self):
        self.tab_recv = ttk.Frame(self.nb)
        self.nb.add(self.tab_recv, text="Receive")
        row = ttk.Frame(self.tab_recv);
        row.pack(fill="x", pady=(10, 6))
        self.recv_led = tk.Canvas(row, width=14, height=14, highlightthickness=0)
        self.recv_led.pack(side="left", padx=(0, 6))
        self._recv_led_id = self.recv_led.create_oval(2, 2, 12, 12, fill="#d9534f", outline="#a94442")  # red
        self.recv_status = tk.StringVar(value="Server: Stopped")
        ttk.Label(row, textvariable=self.recv_status).pack(side="left")
        port_row = ttk.Frame(self.tab_recv); port_row.pack(fill="x", pady=(6, 6))
        ttk.Label(port_row, text="Listen port:").pack(side="left")
        self.entry_port_recv = ttk.Entry(port_row, width=7)
        self.entry_port_recv.pack(side="left", padx=(6, 10))
        self.entry_port_recv.insert(0, self.cfg.get("last_port", "8765"))
        btn_recv = ttk.Button(self.tab_recv, text="Start / Stop", command=self._on_toggle_receive)
        btn_recv.pack(anchor="w", pady=(0, 8))
        sasfrm = ttk.LabelFrame(self.tab_recv, text="SAS confirmation")
        sasfrm.pack(fill="x", pady=(6, 6))
        row1 = ttk.Frame(sasfrm); row1.pack(fill="x", pady=(6, 2))
        ttk.Label(row1, text="SAS:").pack(side="left")
        self.recv_sas_code = tk.StringVar(value="—")
        ttk.Label(row1, textvariable=self.recv_sas_code, font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=6)
        row2 = ttk.Frame(sasfrm); row2.pack(fill="x", pady=(2, 10))
        ttk.Label(row2, text="FP:").pack(side="left")
        self.recv_sas_fp = tk.StringVar(value="—")
        ttk.Label(row2, textvariable=self.recv_sas_fp).pack(side="left", padx=6)
        btns = ttk.Frame(sasfrm); btns.pack(pady=(0, 8))
        ttk.Button(btns, text="Accept", command=self._sas_accept).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel",  command=self._sas_reject).pack(side="left", padx=6)

        # TOFU reset
        tofu_row = ttk.Frame(self.tab_recv); tofu_row.pack(fill="x", pady=(6, 0))
        ttk.Button(tofu_row, text="Reset TOFU (forget all)", command=self._reset_tofu).pack(side="left")

        self.prog_recv = ttk.Progressbar(self.tab_recv, length=400, mode="determinate")
        self.prog_recv.pack(fill="x", pady=(8, 10))

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

    def _build_tab_merge(self):
        self.tab_merge = ttk.Frame(self.nb)
        self.nb.add(self.tab_merge, text="Merge")

        # --- Source / Destination ---
        row1 = ttk.Frame(self.tab_merge)
        row1.pack(fill="x", pady=(10, 4))
        ttk.Label(row1, text="Source DB:").pack(side="left")
        self.entry_merge_src = ttk.Entry(row1, width=60)
        self.entry_merge_src.pack(side="left", padx=6)
        ttk.Button(row1, text="Browse…", command=self._pick_merge_src).pack(side="left")

        row2 = ttk.Frame(self.tab_merge)
        row2.pack(fill="x", pady=(4, 8))
        ttk.Label(row2, text="Destination DB:").pack(side="left")
        self.entry_merge_dst = ttk.Entry(row2, width=60)
        self.entry_merge_dst.pack(side="left", padx=6)
        ttk.Button(row2, text="Browse…", command=self._pick_merge_dst).pack(side="left")

        # --- Options ---
        opts = ttk.Frame(self.tab_merge)
        opts.pack(fill="x", pady=(2, 6))

        self.merge_dry = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Dry-run (read only)", variable=self.merge_dry).pack(side="left")

        self.merge_skip_posters_without_hash = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts,
            text="Skip posters without hash",
            variable=self.merge_skip_posters_without_hash,
        ).pack(side="left", padx=(8, 0))

        self.merge_skip_orphans = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts,
            text="Skip orphans",
            variable=self.merge_skip_orphans,
        ).pack(side="left", padx=(8, 0))

        self.merge_vacuum_optimize = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts,
            text="VACUUM/optimize after merge",
            variable=self.merge_vacuum_optimize,
        ).pack(side="left", padx=(8, 0))

        self.merge_verbose_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts,
            text="Verbose logs",
            variable=self.merge_verbose_log,
        ).pack(side="left", padx=(8, 0))

        # --- Кнопка запуска ---
        self.btn_merge = ttk.Button(self.tab_merge, text="Merge", command=self._run_merge)
        self.btn_merge.pack(anchor="w", pady=(4, 8))

        # --- Прогрессбар ---
        self.prog_merge = ttk.Progressbar(
            self.tab_merge,
            length=400,
            mode="indeterminate",
        )
        self.prog_merge.pack(fill="x", pady=(0, 8))

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

    def _on_progress_send(self, done: int, total: int):
        def upd():
            self._set_progress(self.prog_send, done, total)
            if total and done >= total:
                # маленькая «анимационная» пауза и очистка
                self.after(400, lambda: self._set_progress(self.prog_send, 0, total))
                # чистим SAS на отправителе
                self.send_sas_code.set("—")
                self.send_sas_fp.set("—")

        self.after(0, upd)

    def _on_progress_recv(self, done: int, total: int):
        def upd():
            self._set_progress(self.prog_recv, done, total)
            if total and done >= total:
                # после завершения — чуть подержим 100% и обнулим
                self.after(800, lambda: self._set_progress(self.prog_recv, 0, total))
                # чистим SAS на приёмнике
                self.recv_sas_code.set("—")
                self.recv_sas_fp.set("—")

        self.after(0, upd)

    @staticmethod
    def _set_progress(widget: ttk.Progressbar, done: int, total: int):
        if total and total > 0:
            widget['maximum'] = total
            widget['value'] = min(done, total)

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
                wtr.close();
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
                messagebox.showwarning("Проверка соединения", "Соединение не установлено.", parent=self)

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

        self._log(f"Отправка файла: {path} → {host}:{port}")
        self.nb.select(self.tab_send)

        def sas_info_cb(sas: str, fp: str):
            def upd():
                self.send_sas_code.set(sas)
                self.send_sas_fp.set(fp)
                self._log(f"SAS (sender): {sas} | FP: {fp}")
                self.nb.select(self.tab_send)

            self.after(0, upd)

        # read settings
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

        sender = DBSender(
            chunk_size=chunk_size,
            throttle_kbps=speed_kbps,
            on_progress=self._on_progress_send,
            sas_info=sas_info_cb,
            log=self._log,
            use_gzip=use_gzip,
            vacuum_snapshot=vacuum_snapshot,
        )
        fut = self.asyncio_thread.call(sender.connect_and_send(host, port, path))
        self._pending.append(fut)

        def done_cb(_):
            try:
                self._pending.remove(fut)
            except ValueError:
                pass
            err = fut.exception()
            if err:
                self._log(f"Ошибка отправки: {err}")
                messagebox.showerror("Ошибка", str(err), parent=self)
            else:
                self._log("Отправка завершена")
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
        if not self.receiver_running:
            try:
                port = int(self.entry_port_recv.get().strip() or "8765")
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректный порт", parent=self)
                return

            self.receiver = DBReceiver(
                host="0.0.0.0",
                port=port,
                chunk_dir="./incoming",
                on_progress=self._on_progress_recv,
                sas_confirm=self._sas_confirm_inline,
                on_done=self._on_receive_done,
                log=self._log,
            )
            self._log(f"Запуск приёмника на порту {port} …")
            self.recv_status.set(f"Server: Running on 0.0.0.0:{port}")
            self.receiver_running = True
            self._set_recv_led(True)
            self.asyncio_thread.call(self.receiver.start_listen())
        else:
            self._log("Остановка приёмника …")
            self.recv_status.set("Server: Stopped")
            self.receiver_running = False
            self._set_recv_led(False)
            if self.receiver:
                self.asyncio_thread.call(self.receiver.stop())

    def _reset_tofu(self):
        try:
            if TOFU_FILE.exists():
                # полная очистка
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
            if self.receiver_running and self.receiver:
                self.asyncio_thread.call(self.receiver.stop())
            for fut in list(self._pending):
                try:
                    fut.result(timeout=2)
                except Exception:
                    pass
            try:
                if self._zc:
                    self._zc.close()
            except Exception:
                pass
        finally:
            self.asyncio_thread.stop()
            # NOTE: снапшот теперь удаляется по завершении отправки в DBSender

            self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
