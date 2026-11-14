# 危险区限定探查与悬浮窗合并显示设计

*日期：2026-11-14 · 状态：已确认*

## 1. 背景与目标

当前客户端（`client/albion_aware`）有两个问题：

1. **探查不区分区域**：任何区域都会把非队友玩家列进悬浮窗，任何新玩家都会触发红光与提示音。城市与蓝区里频繁误报。
2. **资源显示在窗外**：gather 模式用独立的左侧 `GatheringPanel` 展示资源，多开一个窗口，拖动/穿透/透明度都要额外同步。

本设计做两件事：

1. **危险区限定**：只有红区、黑区开启玩家探查与告警；进入红/黑区自动打开提示音，回到蓝/黄区自动关闭。
2. **单窗双态**：资源行合并进原悬浮窗，与玩家行二选一显示。有陌生人显示玩家，没有陌生人显示资源。窗口宽度保持 102px 不变。

### 已确认的产品决策

| 决策点 | 结论 |
|---|---|
| 探查区域 | 仅红区、黑区；黄区与蓝区不探查 |
| 资源区域 | 蓝/黄区也显示资源（采集不限于危险区） |
| 资源与模式 | 资源行只在 gather 模式出现，roam 模式行为不变 |
| 资源行排版 | 文字资源名 + 层级.附魔 + 距离 + 方向箭头，宽度不变 |
| 未知区域 | 按“危险”处理并展示玩家，但不自动修改提示音 |

### 非目标

- 不改 Go 后端，不新增协议解析，不新增网络请求。
- 不提供其他玩家的坐标、方位或距离（服务器不下发）。
- 不改变玩家事件仍照常入表的事实：队友自动识别与 F10 手动标记继续可用。
- 不做区域表的在线更新，随客户端版本发布。

## 2. 数据来源

| 数据 | 来源 | 说明 |
|---|---|---|
| 当前区域 ID | `op41` / `op2` 响应（`event_parser.ZoneChanged`） | 已实现，含 `TNL-xxx` 与数字 ID |
| 区域 PvP 等级 | `web/ao-bin-dumps/zones.json` 的 `pvpType` | 1423 个区：safe 569 / yellow 89 / red 74 / black 691，另有 400 个 `TUNNEL_*` |
| 资源节点 | 事件 38/39/40/46 | 已实现，`GatherStore` |
| 自身坐标 | 移动请求 21/22 | 已实现 |
| 非队友玩家 | 事件 29 / 1 / 3 等 + `PartyList` 过滤 | 已实现 |

区域表在打包时生成精简映射，运行时不联网。

## 3. 区域等级判定

新增纯逻辑模块 `client/albion_aware/zone_level.py`，不依赖 tkinter。

### 3.1 数据文件

`client/data/zones.json`：

```json
{"version": 1, "zones": {"1000": "safe", "1007": "yellow", "3005": "red", "5001": "black", "TNL-001": "black"}}
```

- 由 `client/tools/sync_avalon_maps.py` 在现有同步流程中顺带生成，源文件为 `web/ao-bin-dumps/zones.json`。
- 生成规则：取每个区的 `pvpType`；`type` 以 `TUNNEL_` 开头的区一律写 `black`（阿瓦隆之路全局强制黑区，与网页端 `_applyAvalonRoadsRule` 一致）。
- 体积约 25KB，可随包离线分发。

### 3.2 判定顺序

`ZoneLevels.level(zone_id, previous="safe") -> str`：

1. `zone_id` 为空 → 返回 `previous`。
2. 以 `@MISTS` 开头（迷雾/迷雾地牢）→ 返回 `previous`（继承进入迷雾前所在区的等级）。
3. 以 `TNL-` 开头 → `black`。
4. 含 `-` 的复合 ID（如 `1234-5`、`1234-5-2`）→ 取第一段再查表。
5. 查表命中 → 返回该等级。
6. 未命中或无区域表 → `unknown`。

`is_danger(level)`：`red` / `black` 为真；`unknown` 按危险处理的范围由调用方决定（见 6.2）。

区域表加载失败（文件缺失、JSON 损坏）不抛异常，按空表处理，所有区为 `unknown`，并在启动日志记录一次。

## 4. 提示音自动开关

### 4.1 规则

在 `ZoneChanged` 处理时，根据**明确**等级（不含 `unknown`）更新配置：

| 新区域等级 | `overlay.sound` | 图标 |
|---|---|---|
| red / black | 置 `true` 并保存 | 点亮 |
| safe / yellow | 置 `false` 并保存 | 变灰 |
| unknown | 不变 | 不变 |

- 同一等级内反复进出（如红区换红区）不重复写配置。
- 区内仍可手动按 F8 或点图标临时切换；下一次区域切换再按规则重设。
- 托盘菜单的提示音勾选状态读取配置，天然同步。

### 4.2 兜底

- `_play_sound` 除配置外，再要求当前区为探查区（`red` / `black` / `unknown`）。
- 新玩家触发的红光闪烁同样只在探查区执行。
- 这两道判断只作兜底，真正的开关仍由 4.1 的配置驱动。

## 5. 悬浮窗统一显示

### 5.1 内容优先级

```python
def display_mode(mode: str, danger: bool, has_strangers: bool) -> str:
    if danger and has_strangers:
        return "players"
    if mode == "gather":
        return "resources"
    return "empty"
```

| 状态 | 显示 |
|---|---|
| 探查区且有非队友玩家 | 玩家行：武器图标 + IP，最多 `max_rows`（默认 6）行，超出显示 `+N` |
| 探查区且无玩家 | 资源行（gather 模式） |
| 蓝/黄区（不探查） | 资源行（gather 模式） |
| 任意区域 + roam 模式 + 无玩家 | 空窗，只保留顶栏图标行 |

“有非队友玩家”沿用 `PlayerStore.view` 的结果：已排除自己和 `PartyList` 中的队友，并按 `player_timeout`（默认 60 秒）超时清理。

### 5.2 渲染接口

`OverlayWindow` 增加 `render_resources(targets)`，与现有 `render(view, ip_getter)` 并列，两者共用 `_resize(row_count)`：

- `render`：保持不变，渲染玩家行。
- `render_resources`：渲染资源行；对同一批目标用 `targets_hash` 缓存，未变化时跳过重建，避免 0.5 秒刷新导致闪烁。
- `clear()`：清空为 1 行高度，行为不变。

### 5.3 主循环

- `_drain` 每 100ms 调用一次决策；状态（模式、危险、是否有玩家、资源哈希）未变化时不重绘。
- 现有 `_update_gather` 保留 0.5 秒节流，产出 `targets` 后交给悬浮窗渲染（仅 gather 模式）。
- 从 `resources` 切到 `players` 或反向切换时立即重绘，不等待节流。
- 资源行点击不打开详情面板，仅支持拖动窗口；玩家行点击行为不变。

## 6. 资源行排版

### 6.1 尺寸

- 窗口总宽 `WIDTH = 102` 保持不变；扣掉红光 12×2、边框 2×2、行 `padx` 4×2 后，行内容宽约 66px。
- 行高 `ROW_H = 36` 不变；字号 8px。

### 6.2 行结构

```
木  T6.2        23m  ↗
```

| 区域 | 内容 | 样式 |
|---|---|---|
| 左 | 资源短名 | 8px 粗体，使用资源类型色（Log 棕、Rock 灰、Fiber 绿、Hide 褐、Ore 蓝） |
| 中 | `T{tier}.{enchant}` | 8px，前景色 `FG` |
| 右 | `{距离}m` | 8px，弱化色 `MUTED` |
| 最右 | 10×10 Canvas 箭头 | 连续角度，复用现有 `arrow_points` 屏幕空间方位 |

短名（i18n）：

| kind | zh-CN | en |
|---|---|---|
| Log | 木 | LG |
| Rock | 石 | RK |
| Fiber | 纤 | FB |
| Hide | 皮 | HD |
| Ore | 矿 | OR |

### 6.3 数量与排序

- 排序、80 米范围、类型/tier 过滤、`show_living` 全部复用现有 `select_targets` 与 `GatherFilter`，不新增逻辑。
- 数量上限沿用 `gather.max_targets`（默认 5，范围 1–10）。
- 未获取到自身坐标时不显示资源行（空窗），不显示提示文案，避免 66px 宽度溢出。

## 7. 模块改动清单

| 文件 | 变更 |
|---|---|
| `client/albion_aware/zone_level.py` | 新增：区域表加载与等级判定 |
| `client/albion_aware/overlay.py` | 新增 `render_resources`；迁入 `arrow_points`、资源短名配色 |
| `client/albion_aware/main.py` | 接入区域判定、自动提示音、显示决策；移除采集面板接线 |
| `client/albion_aware/gather_panel.py` | 删除 |
| `client/albion_aware/lang/zh-CN.json`、`en.json` | 新增 `gather.short.*`；删除面板专用 `gather.title`、`gather.empty`、`gather.no_position` |
| `client/tools/sync_avalon_maps.py` | 额外生成 `client/data/zones.json` |
| `client/packaging/albion_aware.spec` | datas 增加 `../data/zones.json` |
| `client/tests/test_gather_panel.py` | 删除，箭头测试迁入 `test_overlay.py` |
| `client/tests/test_zone_level.py` | 新增 |
| `client/tests/test_main.py` | 增加 `display_mode` 与提示音决策测试 |
| `client/tests/test_overlay.py` | 增加 `render_resources` 的 resize 几何测试 |

纯函数（便于单测，不依赖 Tk）：

- `zone_level.level(zone_id, previous)` / `is_danger(level)`
- `main.display_mode(mode, danger, has_strangers)`
- `main.sound_for_zone(level, current) -> bool`（`unknown` 返回 `current`）

## 8. 边界处理

| 场景 | 处理 |
|---|---|
| 区域表缺失/损坏 | 全部 `unknown`：展示玩家、不自动改提示音，日志记录一次 |
| 迷雾 | 继承进入前等级；迷雾内再换迷雾继续继承 |
| 阿瓦隆之路 | 一律黑区 |
| 复合 ID `1234-5` | 取 `1234` 查表 |
| 未知新区域 | `unknown`：展示玩家、不自动改提示音（安全优先） |
| 切区 | 现有逻辑清空玩家表与资源表，避免上一区残留 |
| 无自身坐标 | 不渲染资源行，窗口保持最小 1 行高 |
| roam 模式 + 无玩家 | 空窗，仅顶栏 |
| 手动关提示音后进入红区 | 自动重新打开（按 4.1 规则） |
| 红区内手动关提示音 | 生效，直到下一次区域切换 |
| 悬浮窗隐藏 | 资源与玩家都不渲染，F12 恢复后立即按当前状态重绘 |
| 语言切换 | 资源短名与现有 i18n 一起刷新 |

## 9. 测试

单元测试：

- `zone_level`：红/黑/黄/蓝命中、`TNL-001`、`@MISTS@` 继承、复合 ID、空 ID、未知 ID、空表。
- `display_mode`：四种组合。
- `sound_for_zone`：三个明确等级 + `unknown` 保持原值。
- `OverlayWindow.render_resources`：行数决定窗口高度；空列表保持 1 行；宽度恒为 102。
- 箭头几何测试从 `test_gather_panel.py` 迁入 `test_overlay.py`。

手动验证：

- 进城（蓝区）：不列玩家、不响提示音、图标为灰；gather 模式显示资源。
- 进红/黑区：提示音图标自动点亮，出现陌生人立即列行 + 闪红 + 响铃。
- 陌生人离开且超时：自动切回资源行。
- 红区回蓝区：提示音自动关闭，玩家行消失。
- 拖到屏幕左缘时不再出现旧的左侧小窗。

## 10. 已知限制

- 玩家可见范围由服务器决定，探查存在滞后，无法提供方位与距离。
- 区域表随客户端版本更新，新版本新增区域会短暂落到 `unknown`。
- 资源行宽度固定，超长本地化文案只能靠短名规避。
- 迷雾继承依赖“进入迷雾前收到过明确等级”，直接登录进迷雾时按 `safe` 处理。
