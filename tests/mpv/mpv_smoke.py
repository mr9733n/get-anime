import sys, random
import logging
logging.getLogger(__name__).setLevel(logging.CRITICAL)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from app.mpv.mpv_engine import MpvEngine
from app.mpv.player_window import PlayerWindow

URLS = [
    # подставь свои тестовые ссылки
]

def main():
    app = QApplication(sys.argv)
    eng = MpvEngine()
    w = PlayerWindow(eng, autoplay=False, template="no_background_night")
    w.show()

    w.playlist_urls = URLS[:]
    w.playlist_widget.clear()
    for u in w.playlist_urls:
        w.playlist_widget.addItem(u)

    # 100 быстрых переключений
    i = {"n": 0}
    def step():
        if i["n"] >= 100:
            # потом закрываем видео-окно (твой crash-case)
            w.video_window.show()
            QTimer.singleShot(200, w.video_window.close)
            QTimer.singleShot(600, app.quit)
            return
        idx = random.randrange(0, len(w.playlist_urls))
        w.play_index(idx)
        i["n"] += 1
        QTimer.singleShot(30, step)

    QTimer.singleShot(200, step)
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
