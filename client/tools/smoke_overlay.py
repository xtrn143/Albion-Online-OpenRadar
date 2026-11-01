"""界面冒烟：不依赖游戏与雷达，注入 8 个假玩家验证渲染、折叠与闪烁。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from albion_aware.i18n import I18n
from albion_aware.party import PartyList
from albion_aware.player_store import PlayerStore
from albion_aware.overlay import OverlayWindow


def main() -> None:
    i18n = I18n("zh-CN")
    store = PlayerStore(timeout=600.0)
    for index in range(8):
        store.upsert(1000 + index, {"nickname": f"Test{index}"}, now=float(index))

    window = OverlayWindow(
        i18n=i18n,
        icon_loader=lambda _player: None,
        on_row_click=lambda player: print("row click", player.id),
        on_more_click=lambda: print("more click"),
        on_drag_end=lambda x, y: print("dragged", x, y),
    )
    view = store.view(PartyList(), max_rows=6)
    window.render(view, lambda _player: 900)
    window.flash()
    window.run()


if __name__ == "__main__":
    main()
