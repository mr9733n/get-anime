# db_sync_gui.py
import os
import json
import asyncio
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional
from db_transfer import DBReceiver, DBSender
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange


MDNS_SERVICE_TYPE = "_playersync._tcp.local."
CFG_PATH = Path.home() / ".player_db_gui.json"

def load_gui_cfg():
    try:
        if CFG_PATH.exists():
            return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"recent": [], "last_port": "8765"}

def save_gui_cfg(cfg: dict):
    try:
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CFG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, CFG_PATH)
    except Exception:
        pass


# --- простой фоновый asyncio-цикл ---
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
        self.geometry("780x520")
        self['padx'] = 8
        self['pady'] = 8

        self._zc = None
        self._mdns_browser = None
        self._mdns_hosts = set()  # строки "ip:port" или просто ip

        self.asyncio_thread = AsyncioThread()
        self.receiver: Optional[DBReceiver] = None
        self.receiver_running = False
        self._pending = []   # активные задачи отправки
        self._sas_event = None  # для инлайн-подтверждения

        # конфиг GUI
        self.cfg = load_gui_cfg()

        # Notebook с вкладками
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self._build_tab_send()
        self._build_tab_receive()
        self._build_tab_merge()
        self._build_tab_logs()

        self._log("Готово. Используйте вкладки Send/Receive. История адресов сохраняется в ~/.player_db_gui.json.")

    # ---------- ВКЛАДКИ ----------

    def _build_tab_send(self):
        self.tab_send = ttk.Frame(self.nb)
        self.nb.add(self.tab_send, text="Send")

        top = ttk.Frame(self.tab_send);
        top.pack(fill="x", pady=(10, 8))

        ttk.Label(top, text="Receiver:").pack(side="left")
        self.cmb_host = ttk.Combobox(top, width=28, values=self.cfg.get("recent", []))
        self.cmb_host.pack(side="left", padx=(6, 10))
        self.cmb_host.set(self.cfg["recent"][0] if self.cfg.get("recent") else "192.168.0.50")

        ttk.Label(top, text="Port:").pack(side="left")
        self.entry_port_send = ttk.Entry(top, width=7)
        self.entry_port_send.pack(side="left", padx=(6, 10))
        self.entry_port_send.insert(0, self.cfg.get("last_port", "8765"))

        btns = ttk.Frame(self.tab_send);
        btns.pack(fill="x", pady=(0, 8))
        ttk.Button(btns, text="Отправить БД…", command=self._on_send).pack(side="right", padx=6)
        ttk.Button(btns, text="Проверить соединение", command=self._on_check_conn).pack(side="right")

        # mDNS поиск
        md = ttk.Frame(self.tab_send);
        md.pack(fill="x", pady=(0, 6))
        ttk.Button(md, text="Поиск в сети (mDNS)", command=self._start_mdns_browse).pack(side="left")
        self.mdns_status = tk.StringVar(value="mDNS: idle")
        ttk.Label(md, textvariable=self.mdns_status).pack(side="left", padx=10)

        # SAS (sender) — крупно
        sasgrp = ttk.LabelFrame(self.tab_send, text="SAS (sender)")
        sasgrp.pack(fill="x", pady=(6, 6))
        row1 = ttk.Frame(sasgrp);
        row1.pack(fill="x", pady=(6, 2))
        ttk.Label(row1, text="SAS:").pack(side="left")
        self.send_sas_code = tk.StringVar(value="—")
        ttk.Label(row1, textvariable=self.send_sas_code, font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=6)

        row2 = ttk.Frame(sasgrp);
        row2.pack(fill="x", pady=(2, 8))
        ttk.Label(row2, text="FP:").pack(side="left")
        self.send_sas_fp = tk.StringVar(value="—")
        ttk.Label(row2, textvariable=self.send_sas_fp).pack(side="left", padx=6)

        # прогресс отправки
        self.prog_send = ttk.Progressbar(self.tab_send, length=400, mode="determinate")
        self.prog_send.pack(fill="x", pady=(10, 10))

    def _build_tab_receive(self):
        self.tab_recv = ttk.Frame(self.nb)
        self.nb.add(self.tab_recv, text="Receive")

        row = ttk.Frame(self.tab_recv);
        row.pack(fill="x", pady=(10, 6))

        # индикатор (красный по умолчанию)
        self.recv_led = tk.Canvas(row, width=14, height=14, highlightthickness=0)
        self.recv_led.pack(side="left", padx=(0, 6))
        self._recv_led_id = self.recv_led.create_oval(2, 2, 12, 12, fill="#d9534f", outline="#a94442")  # red

        self.recv_status = tk.StringVar(value="Server: Stopped")
        ttk.Label(row, textvariable=self.recv_status).pack(side="left")

        # порт для приёмника
        port_row = ttk.Frame(self.tab_recv); port_row.pack(fill="x", pady=(6, 6))
        ttk.Label(port_row, text="Listen port:").pack(side="left")
        self.entry_port_recv = ttk.Entry(port_row, width=7)
        self.entry_port_recv.pack(side="left", padx=(6, 10))
        self.entry_port_recv.insert(0, self.cfg.get("last_port", "8765"))

        btn_recv = ttk.Button(self.tab_recv, text="Start / Stop", command=self._on_toggle_receive)
        btn_recv.pack(anchor="w", pady=(0, 8))

        # Инлайн-панель SAS подтверждения
        sasfrm = ttk.LabelFrame(self.tab_recv, text="SAS подтверждение")
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
        ttk.Button(btns, text="Принять", command=self._sas_accept).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена",  command=self._sas_reject).pack(side="left", padx=6)

        # прогресс приёма (тот же индикатор можно использовать, если хочешь)
        self.prog_recv = ttk.Progressbar(self.tab_recv, length=400, mode="determinate")
        self.prog_recv.pack(fill="x", pady=(8, 10))

    def _set_recv_led(self, running: bool):
        # цвета: зелёный (#5cb85c) / красный (#d9534f)
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
        ttk.Label(self.tab_merge, text="Здесь появится интерфейс слияния БД (merge).").pack(anchor="w", padx=4, pady=8)

    def _build_tab_logs(self):
        self.tab_logs = ttk.Frame(self.nb)
        self.nb.add(self.tab_logs, text="Logs")
        self.txt = tk.Text(self.tab_logs, height=14)
        self.txt.pack(fill="both", expand=True)

    # ---------- ЛОГИ/ПРОГРЕСС ----------

    def _log(self, s: str):
        self.txt.insert("end", s + "\n")
        self.txt.see("end")

    def _on_progress_send(self, done: int, total: int):
        self.after(0, lambda: self._set_progress(self.prog_send, done, total))

    def _on_progress_recv(self, done: int, total: int):
        self.after(0, lambda: self._set_progress(self.prog_recv, done, total))

    @staticmethod
    def _set_progress(widget: ttk.Progressbar, done: int, total: int):
        if total and total > 0:
            widget['maximum'] = total
            widget['value'] = min(done, total)

    # --- Utils

    def _start_mdns_browse(self):
        # один браузер на приложение
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
            self._log("mDNS: поиск приёмников…")
            # через 3 сек зафиксируем список
            self.after(3000, self._finish_mdns_scan)
        except Exception as e:
            self.mdns_status.set("mDNS: error")
            self._log(f"mDNS error: {e}")

    def _on_mdns_service(self, zeroconf, service_type, name, state_change):

        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return
            # извлечём адреса
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
            # подставим в combobox (только ip:port)
            self.cmb_host["values"] = items + list(self.cfg.get("recent", []))
            # оставим в поле только ip (без :port), порт в отдельном поле
            # если хочешь с портом сразу — распарь ниже
            first = items[0]
            if ":" in first:
                ip, p = first.split(":")
                self.cmb_host.set(ip)
                self.entry_port_send.delete(0, "end")
                self.entry_port_send.insert(0, p)
            self.mdns_status.set(f"mDNS: found {len(items)}")
            self._log(f"mDNS: найдено {len(items)} приёмников")
        else:
            self.mdns_status.set("mDNS: none")
            self._log("mDNS: приёмники не найдены")

    def _on_check_conn(self):
        host = self.cmb_host.get().strip()
        try:
            port = int(self.entry_port_send.get().strip() or "8765")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректный порт", parent=self)
            return

        self._log(f"Проверка соединения: {host}:{port} …")

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

        sender = DBSender(
            on_progress=self._on_progress_send,
            sas_info=sas_info_cb
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
                # сохранить адрес в историю
                addr = f"{host}"
                recent = [addr] + [x for x in self.cfg.get("recent", []) if x != addr]
                self.cfg["recent"] = recent[:8]
                self.cfg["last_port"] = str(port)
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
                sas_confirm=self._sas_confirm_inline
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

    # инлайн подтверждение SAS в вкладке Receive
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
            self._sas_event["ok"] = True
            self._sas_event["ev"].set()

    def _sas_reject(self):
        if self._sas_event:
            self._sas_event["ok"] = False
            self._sas_event["ev"].set()

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
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
