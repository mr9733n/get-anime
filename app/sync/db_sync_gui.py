# db_sync_gui.py
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

from db_transfer import DBReceiver, DBSender

# --- вспомогательный класс для фонового asyncio цикла ---
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

# --- GUI приложение ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Player DB Sync (LAN)")
        self.geometry("640x420")
        self['padx'] = 10; self['pady'] = 10

        self.asyncio_thread = AsyncioThread()
        self.receiver: Optional[DBReceiver] = None
        self.receiver_running = False

        # UI элементы
        frm = ttk.Frame(self); frm.pack(fill="x", pady=(0, 10))
        ttk.Label(frm, text="Receiver IP:").pack(side="left")
        self.entry_ip = ttk.Entry(frm, width=24)
        self.entry_ip.pack(side="left", padx=(5, 10))
        self.entry_ip.insert(0, "192.168.0.52")  # пример

        ttk.Label(frm, text="Port:").pack(side="left")
        self.entry_port = ttk.Entry(frm, width=6)
        self.entry_port.pack(side="left", padx=(5, 10))
        self.entry_port.insert(0, "8765")

        btn_send = ttk.Button(frm, text="Отправить БД…", command=self._on_send)
        btn_send.pack(side="right")

        btn_recv = ttk.Button(self, text="Принять (старт/стоп)", command=self._on_toggle_receive)
        btn_recv.pack(fill="x")

        # прогресс
        self.prog = ttk.Progressbar(self, length=400, mode="determinate")
        self.prog.pack(fill="x", pady=(10, 10))

        # лог
        self.txt = tk.Text(self, height=12)
        self.txt.pack(fill="both", expand=True)
        self._log("Готово. Укажите IP и нажмите «Отправить БД…» или нажмите «Принять».")

    def _log(self, s: str):
        self.txt.insert("end", s + "\n")
        self.txt.see("end")

    # колбэк SAS для Sender/Receiver
    def _sas_confirm(self, role: str):
        def inner(sas_code: str, fp: str) -> bool:
            result = {"ok": False}
            ev = threading.Event()
            def prompt():
                msg = (
                    f"Роль: {role}\n"
                    f"SAS-код: {sas_code}\n"
                    f"Отпечаток пира: {fp}\n\n"
                    "Коды совпадают на обоих устройствах?"
                )
                result["ok"] = messagebox.askyesno("Подтвердите пару", msg, parent=self)
                ev.set()
            # показать диалог в главном (UI) потоке
            self.after(0, prompt)
            ev.wait()
            return result["ok"]
        return inner

    # прогресс-колбэк
    def _on_progress_recv(self, done: int, total: int):
        self._update_progress(done, total)
    def _on_progress_send(self, done: int, total: int):
        self._update_progress(done, total)
    def _update_progress(self, done: int, total: int):
        self.after(0, lambda: self._set_progress(done, total))
    def _set_progress(self, done: int, total: int):
        if total > 0:
            self.prog['maximum'] = total
            self.prog['value'] = done

    def _on_toggle_receive(self):
        if not self.receiver_running:
            port = int(self.entry_port.get().strip() or "8765")
            # создать приёмник
            self.receiver = DBReceiver(
                host="0.0.0.0",
                port=port,
                chunk_dir="./incoming",
                on_progress=self._on_progress_recv,
                sas_confirm=self._sas_confirm("Receiver"),
            )
            self._log(f"Запуск приёмника на порту {port} …")
            self.receiver_running = True
            # старт в фоне
            self.asyncio_thread.call(self.receiver.start_listen())
        else:
            self._log("Остановка приёмника …")
            self.receiver_running = False
            if self.receiver:
                self.asyncio_thread.call(self.receiver.stop())

    def _on_send(self):
        host = self.entry_ip.get().strip()
        port = int(self.entry_port.get().strip() or "8765")
        if not host:
            messagebox.showerror("Ошибка", "Укажите IP адрес приёмника", parent=self)
            return
        # выбрать файл БД
        path = filedialog.askopenfilename(
            title="Выберите SQLite БД",
            filetypes=[("SQLite DB", "*.db;*.sqlite;*.sqlite3"), ("All files", "*.*")]
        )
        if not path:
            return
        self._log(f"Отправка файла: {path} → {host}:{port}")
        def sas_info_cb(sas: str, fp: str):
            # важно вызывать из UI-потока
            self.after(0, lambda: self._log(f"SAS (sender): {sas}  |  FP: {fp}"))

        sender = DBSender(
            on_progress=self._on_progress_send,
            # отправителю подтверждение не нужно:
            # sas_confirm=self._sas_confirm("Sender"),
            sas_info=sas_info_cb
        )
        # запустить в фоне
        fut = self.asyncio_thread.call(sender.connect_and_send(host, port, path))
        # добавить колбэк завершения (для логов)
        def done_cb(_):
            err = fut.exception()
            if err:
                self._log(f"Ошибка отправки: {err}")
                messagebox.showerror("Ошибка", str(err), parent=self)
            else:
                self._log("Отправка завершена")
        fut.add_done_callback(done_cb)

    def on_close(self):
        try:
            if self.receiver_running and self.receiver:
                self.asyncio_thread.call(self.receiver.stop())
        finally:
            self.asyncio_thread.stop()
            self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
