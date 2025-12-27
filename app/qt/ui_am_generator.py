# app/qt/ui_am_generator.py
import base64
import html
from urllib.parse import quote
import logging
from typing import Callable, Iterable, Optional

from PyQt5.QtWidgets import QVBoxLayout, QWidget, QTextBrowser

from utils.media.image_manager import guess_mime
from utils.parsing.animedia import parse_schedule_line

PROVIDER_ANIMEDIA = "animedia"
SHOW_AM_SCHEDULE = "animedia_schedule"
SHOW_AM_TITLES = "animedia_titles"
SCHEDULE_KEY: str = "am_schedule_cache"
ALL_TITLES_KEY: str = "am_all_titles_cache"


class UIAMGenerator:
    def __init__(self, app, db_manager, template_name):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager
        self.current_template = template_name

    def create_animedia_schedule_browser(self, schedule):
        try:
            html_text = self._generate_page(
                mode=SHOW_AM_SCHEDULE,
                blocks=schedule,
                title_text="Новые серии аниме с сайта AniMedia",
                hint_text="Нажми на название или постер, чтобы отобразить.",
                refresh_href=f"refresh_display/{SHOW_AM_SCHEDULE}",
                reload_poster_href=f"reload_poster/",
                parse_key=SCHEDULE_KEY,
                poster_size_key="small",
                poster_w=80,
                poster_h=112,
                section_title_fn=self._section_title_schedule,
                meta_fn=lambda time_part, ep_part, rating: self._meta_join(time_part, ep_part),
            )
            return self._create_browser_layout(html_text)
        except Exception as e:
            self.logger.error(f"Error create_animedia_schedule_browser: {e}", exc_info=True)
            return None

    def create_animedia_titles_browser(self, titles):
        try:
            html_text = self._generate_page(
                mode=SHOW_AM_TITLES,
                blocks=titles,
                title_text="Все аниме с сайта AniMedia",
                hint_text="Нажми на название или постер, чтобы отобразить.",
                refresh_href=f"refresh_display/{SHOW_AM_TITLES}",
                reload_poster_href=f"reload_poster/",
                parse_key=ALL_TITLES_KEY,
                poster_size_key="medium",
                poster_w=213,
                poster_h=300,
                section_title_fn=self._section_title_titles,
                meta_fn=lambda time_part, ep_part, rating: self._meta_join(
                    (f"★ {rating:.1f}" if isinstance(rating, float) and rating > 0 else None),
                    ep_part
                ),
            )
            return self._create_browser_layout(html_text)
        except Exception as e:
            self.logger.error(f"Error create_animedia_titles_browser: {e}", exc_info=True)
            return None

    def _create_browser_layout(self, html_text: str):
        layout = QVBoxLayout()

        container_widget = QWidget(self.app)
        container_layout = QVBoxLayout(container_widget)

        browser = QTextBrowser(container_widget)
        browser.anchorClicked.connect(self.app.on_link_click)
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("""
            text-align: left;
            border: 1px solid #444;
            color: #000;
            font-size: 12pt;
            font-weight: normal;
            background: rgba(255, 255, 255, 0.5);
        """)
        browser.setHtml(html_text)

        container_layout.addWidget(browser)
        layout.addWidget(container_widget)
        return layout

    def _generate_page(
        self,
        mode: str,
        blocks,
        title_text: str,
        hint_text: str,
        refresh_href: str,
        reload_poster_href: str,
        parse_key: str,
        poster_size_key: str,
        poster_w: int,
        poster_h: int,
        section_title_fn: Callable[[Optional[int]], str],
        meta_fn: Callable[[str, str, Optional[str]], str],
    ) -> str:
        _, _, _, styles_css = self.db_manager.get_template(self.current_template)

        if not blocks:
            empty = "Нет данных AniMedia для отображения." if mode == SHOW_AM_TITLES else "Нет данных расписания AniMedia."
            return f"<div style='padding:20px; font-size:14pt;'>{empty}</div>"

        rows: list[str] = []
        rows.append(f"""<style>{styles_css}</style>""")
        rows.append(f"""
                      <div style="padding:18px;">
                          <div style="font-size:20pt; font-weight:bold; margin-bottom:10px;">
                            {html.escape(title_text)}
                                <div class="am-toolbar">
                                    <a class="am-iconbtn" href="{refresh_href}">
                                        <table cellspacing="0" cellpadding="0" style="display:inline-table; vertical-align:middle;">
                                            <tr>
                                                <td style="vertical-align:middle; padding-right:8px;">
                                                    <div style="opacity:0.8; margin-bottom:18px; font-weight:bold;">
                                                        {html.escape(hint_text)}
                                                    </div>
                                                </td>
                                                <td style="vertical-align:middle; padding-right:8px;">
                                                    <span class="am-icon">🔄</span>
                                                </td>
                                                <td style="vertical-align:middle; margin: 10px 10px 10px 10px">
                                                    REFRESH SCREEN
                                                </td>
                                            </tr>
                                        </table>
                                    </a>
                                </div>
                            </div>
                      </div>
                    """)

        for block in blocks:
            page = block.get("page")
            titles = block.get("titles") or []
            if not titles:
                continue

            section_title = section_title_fn(page)
            if section_title:
                rows.append(f"<div style='margin:16px 0 8px; font-size:14pt; font-weight:bold;'>{section_title}</div>")

            rows.append(self._render_two_col_grid(
                titles=titles,
                parse_key=parse_key,
                poster_size_key=poster_size_key,
                poster_w=poster_w,
                poster_h=poster_h,
                meta_fn=meta_fn,
                reload_poster_href=reload_poster_href,
            ))

        rows.append("</div>")
        return "\n".join(rows)

    def _render_two_col_grid(
        self,
        titles: Iterable[str],
        parse_key: str,
        poster_size_key: str,
        poster_w: int,
        poster_h: int,
        meta_fn: Callable[[str, str, Optional[str]], str],
        reload_poster_href: str,
    ) -> str:
        rows: list[str] = []
        rows.append("<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:8px;'>")

        col = 0
        for line in titles:
            title, time_part, ep_part, rating, poster, original_id = parse_schedule_line(parse_key, line)

            safe_title = html.escape(title)
            href = "am_search/" + quote(title) + "/" + (original_id or "")

            if not original_id:
                return ""

            title_db = self.db_manager.get_title_by_external_id(PROVIDER_ANIMEDIA, original_id)
            if not title_db:
                return ""
            title_id = title_db.title_id
            reload_poster = reload_poster_href + f"{title_id}/{poster_size_key}"

            img_html = self._get_poster_img_html(
                title_id=title_id,
                size_key=poster_size_key,
                w=poster_w,
                h=poster_h,
            )

            meta_text = meta_fn(time_part or "", ep_part or "", rating)

            card_html = self._render_card(
                href=href,
                safe_title=safe_title,
                img_html=img_html,
                meta_text=meta_text,
                poster_w=poster_w,
                poster_h=poster_h,
                reload_poster_href=reload_poster,
            )

            if col == 0:
                rows.append("<tr>")
            rows.append(f"<td width='50%' valign='top'>{card_html}</td>")
            col = 1 - col
            if col == 0:
                rows.append("</tr>")

        if col == 1:
            rows.append("<td width='50%'></td></tr>")

        rows.append("</table>")
        return "\n".join(rows)

    def _render_card(
        self,
        href: str,
        safe_title: str,
        img_html: str,
        meta_text: str,
        poster_w: int,
        poster_h: int,
        reload_poster_href: str,
    ) -> str:
        placeholder = (
            f"<div style='width:{poster_w}px; height:{poster_h}px; background:rgba(0,0,0,0.06); border-radius:6px;'></div>"
        )
        img_or_placeholder = img_html or placeholder
        reload_poster_html = f"""<div class="am-toolbar">
                                      <a class="am-iconbtn" href="{reload_poster_href}">
                                        <table cellspacing="0" cellpadding="0" style="display:inline-table; vertical-align:middle;">
                                          <tr>
                                            <td style="vertical-align:middle; padding-right:8px;">
                                              <span class="am-icon">⟳</span>
                                            </td>
                                            <td style="vertical-align:middle; margin: 10px 10px 10px 10px">
                                              RELOAD POSTER
                                            </td>
                                          </tr>
                                        </table>
                                      </a>
                                    </div>
                                """
        return f"""
        <table width="100%" cellspacing="0" cellpadding="0" class="am-card" style="margin:6px 6px;">
          <tr>
            <td width="{poster_w + 12}" valign="top" style="padding:10px;">
              <a href="{href}">{img_or_placeholder}</a>
            </td>
            <td valign="top" style="padding:10px 10px 10px 0;">
              <div class="am-title">
                <a href="{href}">{safe_title}</a>
              </div>
              <div class="am-meta">{html.escape(meta_text) if meta_text else ""}</div>
              <div class="am-toolbar">{reload_poster_html}</div>
            </td>
          </tr>
        </table>
        """

    def _get_poster_img_html(self, title_id: str, size_key: str, w: int, h: int) -> str:
        if not title_id:
            return ""

        try:
            poster_data = self.app.get_poster_or_placeholder(title_id, size_key=size_key)
            if not poster_data:
                return ""
            mime = guess_mime(poster_data)
            b64 = base64.b64encode(poster_data).decode("ascii")
            return f"<img src='data:{mime};base64,{b64}' width='{w}' height='{h}' style='border-radius:6px;'/>"
        except Exception:
            return ""

    @staticmethod
    def _section_title_schedule(page: Optional[int]) -> str:
        if page is None:
            return ""
        return f"Новые серии аниме [{page}]" if page != 0 else "Сегодня выйдет"

    @staticmethod
    def _section_title_titles(page: Optional[int]) -> str:
        if page is None:
            return "Каталог аниме"
        return f"Страница [{page}]" if page else "Каталог AniMedia"

    @staticmethod
    def _meta_join(*parts) -> str:
        items = []
        for p in parts:
            if p is None:
                continue
            if isinstance(p, float):
                if p <= 0:
                    continue
                items.append(f"{p:.1f}")  # 8.2
                continue
            s = str(p).strip()
            if s:
                items.append(s)
        return " — ".join(items)
