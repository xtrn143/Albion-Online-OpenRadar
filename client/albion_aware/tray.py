# client/albion_aware/tray.py
"""系统托盘：菜单动作由 main 注入。"""
import pystray
from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (18, 18, 18, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 6, size - 6, size - 6), outline=(255, 59, 48, 255), width=4)
    draw.line((16, size // 2, size - 16, size // 2), fill=(214, 214, 214, 255), width=4)
    return image


def build_tray(i18n, actions: dict) -> pystray.Icon:
    def wrap(name, *args):
        def handler(_icon, _item):
            actions[name](*args)
        return handler

    menu = pystray.Menu(
        pystray.MenuItem(i18n.t("tray.show"), wrap("toggle_visible"), default=True),
        pystray.MenuItem(i18n.t("tray.click_through"), wrap("click_through")),
        pystray.MenuItem(i18n.t("tray.map_lookup"), wrap("map_lookup")),
        pystray.MenuItem(i18n.t("tray.reset_position"), wrap("reset_position")),
        pystray.MenuItem(i18n.t("tray.sound"), wrap("toggle_sound"),
                         checked=lambda _item: bool(actions.get("sound_on", lambda: False)())),
        pystray.MenuItem(i18n.t("tray.opacity"), pystray.Menu(
            pystray.MenuItem("100%", wrap("set_opacity", 1.0)),
            pystray.MenuItem("90%", wrap("set_opacity", 0.9)),
            pystray.MenuItem("80%", wrap("set_opacity", 0.8)),
            pystray.MenuItem("70%", wrap("set_opacity", 0.7)),
        )),
        pystray.MenuItem(i18n.t("tray.language"), pystray.Menu(
            pystray.MenuItem(i18n.t("tray.language.auto"), wrap("set_language", "auto")),
            pystray.MenuItem(i18n.t("tray.language.zh"), wrap("set_language", "zh-CN")),
            pystray.MenuItem(i18n.t("tray.language.en"), wrap("set_language", "en")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(i18n.t("tray.feedback"), wrap("feedback")),
        pystray.MenuItem(i18n.t("tray.about"), wrap("about")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(i18n.t("tray.quit"), wrap("quit")),
    )
    return pystray.Icon("AlbionAware", create_icon(), i18n.t("app.title"), menu)
