# 阿瓦隆查图（Avalon Map Lookup）— 设计文档

- 日期：2026-11-05
- 状态：待用户审阅
- 关联产品：AlbionAware 悬浮窗（`client/albion_aware`），上游 OpenRadar（MIT）
- 参考实现：https://portaler.pages.dev/maps

## 1. 目标

玩家进入阿瓦隆之路（`mapId` 为 `TNL-xxx`）后，按 `F6` 呼出查图窗，用游戏里看到的区名（两段式/三段式）快速定位并查看该区地图截图，看到资源构成与阶数。

成功标准：

- 玩家按习惯输入（如 `HET LUA`、`HET-LUA`、`HETLUA`、`SEC QI ODE`、`SECQODE`、完整区名）均能命中目标区。
- 输入唯一确定时地图立即展示，无需额外回车。
- 断网环境下可用（全量离线内置）。
- 不干扰主悬浮窗与玩家视野；`Esc` 一键退出。

非目标（Out of Scope）：

- 不在截图之上重新标注资源/门位置（截图本身已含游戏内地图元素）。
- 不做门→目标区的实时解析（协议层不存在该映射，见项目记忆 2026-11-01 结论）。
- 不做联网共享、战绩统计、路线规划。
- 不改造 OpenRadar 上游 Web UI。

## 2. 架构

```
构建期
  web/ao-bin-dumps/zones.json (TNL 400)  ─┐
  avalon-gold-finder/data.json (400)     ─┼─► tools/sync-avalon-maps ─► client/data/avalon/
  avalon-gold-finder/maps/*.webp (397)   ─┘      index.json + maps/*.webp

运行期
  OpenRadar WS ─► radar_client ─► event_parser(ZoneChanged) ─► AlbionAwareApp
                                                             ├─ in_roads 状态（TNL-xxx）
                                                             ├─ 主悬浮窗 5s 金点
                                                             └─ F6 ─► MapWindow
                                                                      ├─ AvalonMapIndex（纯 Python）
                                                                      └─ 图片 LRU 缓存
```

新增模块：

| 模块 | 职责 | 依赖 |
|---|---|---|
| `map_index.py` | 加载 `index.json`、构建速记键、三级匹配与排序；纯 Python，无 UI | json / dataclasses |
| `map_window.py` | Tk Toplevel：搜索框、候选列表、地图画布（缩放/拖动） | tkinter、Pillow、map_index |
| `tools/sync-avalon-maps` | 构建期同步/下载地图与索引，生成 `client/data/avalon/index.json` | Node 或 Python 均可 |

## 3. 数据

### 3.1 来源与合并

| 来源 | 内容 | 用途 |
|---|---|---|
| `web/ao-bin-dumps/zones.json` | 键 `TNL-001..TNL-400`，值含 `name / tier / type / pvpType / file / bounds` | 权威区名、阶数、当前区 id→区名 |
| `avalon-gold-finder/public/data.json` | `[{name, tier, icons:[{alt,badge?}], img, missing_screenshot}]` | 资源图标与截图文件名 |
| `avalon-gold-finder/public/maps/*.webp` | 1546×1068 游戏截图，397 张，18.8MB | 地图显示 |

合并规则：

- 归一化键 `norm(name) = name.lower()` 去掉 `-`、`_`、空格。
- 实测：400 个 TNL 区名与 400 条图库记录按 `norm` **100% 对齐**（仅 6 条大小写差异，如 zones 的 `Sectun-Oc-Odesis` 与图库的 `Sectun-OC-Odesis`）。
- 以 `zones.json` 的区名/阶数为准；`data.json` 提供 `icons` 与图片文件名。
- `zones.json` 中 `TNL-201..400` 与 `TNL-001..200` 存在 200 组共享布局（`file` 相同），但**区名不同**，因此按 400 个独立条目建索引，不做去重。

### 3.2 索引文件 `client/data/avalon/index.json`

```json
{
  "version": 1,
  "generated_at": "2026-11-05T00:00:00Z",
  "maps": [
    {
      "name": "Hetitos-Iuaerom",
      "tier": 6,
      "parts": ["Hetitos", "Iuaerom"],
      "key3": "HETIUA",
      "icons": [{"alt": "GOLD", "badge": 2}, {"alt": "ORE"}],
      "imgFile": "Hetitos-Iuaerom T6.webp",
      "zoneIds": ["TNL-225"]
    }
  ]
}
```

- `key3`：每段取前 3 个字母（不足 3 取全段）后大写拼接；400 条零碰撞（已实测）。
- `zoneIds`：允许一个区名对应多个 TNL 键（当前数据为 1:1，保留扩展）。
- 索引体量约 250KB，入库版本控制；`maps/*.webp` 18.8MB **不入库**（`.gitignore`），由构建前同步。

### 3.3 构建期同步

`tools/sync-avalon-maps`（`build.ps1` 调用，幂等）：

1. 若本机存在 `D:\work\avalon-gold-finder\public\{data.json,maps}` → 直接读取。
2. 否则从 `https://portaler.pages.dev/data.json` 与 `/maps/<img 路径>.webp` 下载到临时目录。
3. 生成 `client/data/avalon/index.json` 并复制图片到 `client/data/avalon/maps/`。
4. 图片缺失（`missing_screenshot=true` 或下载 404）时仍保留索引条目，运行期显示占位。

## 4. 匹配算法

纯函数接口：

```python
class AvalonMapIndex:
    def load(self, index_path: Path) -> None
    def query(self, text: str, *, current_zone: str | None = None,
              history: list[str] = (), limit: int = 8) -> list[MapHit]
```

`MapHit`：`entry / matched_parts / score / is_current`。

### 4.1 归一化

```
upper(text)；字符折叠（I↔L、O↔0、1↔I 统一折叠，解决游戏字体里大写 I 与 l 难分辨）；
去掉 -、_、空格后的紧凑串 compact；
按 [-_空格]+ 切分得到 tokens（保留顺序与大小写不敏感）。
```

字符折叠是必要的：`Hetitos-Iuaerom` 的第二段在游戏字体里常被读成 `luaerom`，玩家会输入 `HET LUA`；折叠后 `HET LUA → HETIUA` 与速记键一致。实测对 400 条区名做 I↔L 折叠后，速记键仍零碰撞。

### 4.2 三级流水

| 级别 | 条件 | 分值 |
|---|---|---|
| L1 速记键 | `compact == key3` | 1000 |
| L2a 分隔输入 | 有分隔符，token[i] 是第 i 段的前缀（允许少输后面的段） | 600 + 40×命中字符数 + 30×命中的段数 |
| L2b 紧凑 DP | 无分隔符，DP 把 compact 切成与段数相同的若干块，每块为对应段前缀 | 550 + 40×命中字符数 + 30×命中段数 |
| L3 模糊 | 各段前缀匹配失败，但按段计算编辑距离 ≤1 | 300 + 10×命中段数 |

DP 规则（L2b）：

- `dp[i][j]` = 用前 i 段匹配 compact 前 j 个字符是否可行；转移枚举第 i 段消耗 `k` 个字符（`k` 从段长上限递减）。
- 优先级：`k == 3` > `k == 2` > 其他；要求 `compact[j-k:j]` 是该段的前缀。
- 允许末尾少匹配段（玩家只输入前两段的前缀），缺段按 0 分计但保留候选。

### 4.3 排序

降序比较：

1. 当前所在区（`current_zone ∈ entry.zoneIds`）→ +200
2. 最近查过（history 越靠前加分越少）→ +50
3. 含 `GOLD` 图标 → +10
4. 阶数：T8 > T6 > T4（+8 / +5 / +2）
5. 名称字母序（稳定兜底）

任一查询命中多条时返回前 8 条；命中恰好 1 条即视为唯一命中，窗口自动展示地图。

### 4.4 输入示例（设计验收用例）

| 输入 | 期望 |
|---|---|
| `HET LUA` / `HET-LUA` / `HET_LUA` / `HETLUA` | 折叠后均为 `HETIUA`，首位命中 `Hetitos-Iuaerom`（TNL-225） |
| `HET IUA` / `HETIUA` | 同上，不依赖 I/L 折叠也命中 |
| `SEC QI ODE` / `SECQIODE` | 首位命中 `Secent-Qi-Odesom`（TNL-377） |
| 完整区名（含分隔符） | L1 或 L2a 首位命中 |
| `HETLUB` | L3 兜底仍能出候选 |
| 空输入 | 返回当前区（若在 Roads）与历史，最多 8 条 |

## 5. 界面与交互

### 5.1 查图窗

- Toplevel，默认 720×560，居中偏上（水平居中、垂直 18%），位置持久化到 `config.overlay.map_x/map_y`。
- `-topmost` 且打开时 `SetForegroundWindow` + 搜索框 `focus_force`；关闭后焦点交还游戏。
- 布局：
  - 顶部：搜索图标 + 输入框 + 结果计数 + 关闭 `×`。
  - 候选列表：最多 8 行，每行 = 区名 + `T{n}` + `💎`（有金箱时）+ 资源小图标（9 类，带数量角标）+ “当前”标签。
  - 地图画布：`PIL.Image` → `ImageTk.PhotoImage`，按画布宽度自适应初始缩放。
  - 底部：键位提示 `F6 开关 · Enter 查看 · ↑↓ 选择 · Esc 关闭`。
- 缩放/平移：滚轮 0.5×–2.0×（以鼠标位置为锚点），左键拖动，双击复位适屏。
- 图像 LRU：最多保留 5 张已解码图，切换候选时释放旧引用。

### 5.2 键位

| 键 | 行为 |
|---|---|
| `F6` | 打开/关闭查图窗（全局热键） |
| `Esc` | 关闭 |
| `↑` / `↓` | 移动候选选中 |
| `Enter` | 展示选中项的地图 |
| `Tab` | 补全为第一条候选的完整区名 |

### 5.3 打开时的默认状态

- 在 Roads（`TNL-xxx`）：预填当前区名并自动出图，输入框内容全选，直接键入即覆盖。
- 不在 Roads：空输入，列表显示历史（最近 10 条）+ 热门（含 Gold，按阶数排序）各取若干。
- 失焦**不自动关闭**（避免游戏全屏切换误关）。

## 6. 系统集成

| 位置 | 改动 |
|---|---|
| `config.py` | 新增 `hotkeys.map_lookup = "F6"`、`overlay.map_x/map_y = null` |
| `main.py` | 注册 F6 → 队列动作 `_queue_open_maps`；`ZoneChanged` 时维护 `in_roads`、触发金点计时 |
| `overlay.py` | 顶部图标行新增金色小点（5 秒后消失），点击打开查图窗 |
| `tray.py` | 菜单新增“阿瓦隆查图 (F6)” |
| `i18n` | 新增 `map.*`：标题、搜索提示、无结果、当前区、资源名（金箱/蓝箱/绿箱/地下城/木材/矿石/石头/纤维/兽皮）、底栏提示、数据缺失 |
| `albion_aware.spec` | `datas` 增加 `("../data/avalon", "data/avalon")` |
| `build.ps1` | 构建前执行 `tools/sync-avalon-maps` |
| `NOTICE.txt` / `README.txt` | 声明地图数据来源（avalon-gold-finder、portaler.pages.dev） |

热键说明：`F7/F8/F9/F10` 已被提示音/显隐/标记队友/穿透占用，`F6` 为默认空闲键，可在配置文件修改。

## 7. 错误处理

| 场景 | 处理 |
|---|---|
| 索引缺失/JSON 损坏 | 查图窗显示“地图数据缺失，请重新安装”；主悬浮窗不受影响 |
| 图片文件缺失 | 显示“该区暂无截图”占位，仍显示区名/T 阶/资源 |
| 当前区 TNL 不在索引（游戏新版本） | 仍可搜索全部条目，当前区提示“当前区暂无地图数据” |
| 首次打开慢 | 索引与首张图在工作线程加载，窗口先显示“加载中” |
| 焦点被游戏抢占 | `SetForegroundWindow` + `focus_force`，窗口保持 `-topmost` |
| 热键注册失败（被其他软件占用） | 托盘提示“F6 被占用，可在配置中修改”，托盘菜单仍可打开 |

## 8. 测试

- `test_map_index.py`：
  - `key3` 生成与归一化；
  - L1/L2a/L2b/L3 各输入样例（4.4 表）；
  - 排序：当前区置顶、历史优先、Gold、阶数；
  - `limit` 截断与 `unique` 判定；
  - 索引缺失时抛可捕获错误。
- `test_map_window.py`（不渲染真实 Tk）：
  - 键位映射（↑↓/Enter/Tab/Esc）；
  - 打开时预填当前区；
  - 候选切换后图像引用释放。
- 扩展 `test_smoke.py`：查图窗开关、滚轮缩放调用的冒烟。
- 手动验收：
  1. 进入 Roads → 主窗金点出现并在 5 秒后消失；
  2. `F6` → 预填当前区并出图；
  3. 输入 `HETLUA` → 自动出图；`HET` → 候选列表；
  4. 滚轮缩放、拖动、双击复位；
  5. 托盘菜单打开；
  6. 断网重复上述步骤。
- 打包验收：`build.ps1` 后安装包内 `data/avalon/` 含索引与全部图片（缺失数 ≤ 2），安装后断网可用。

## 9. 风险与已知限制

| 风险 | 说明 |
|---|---|
| 游戏新增/改名区 | 索引需随上游 data 更新；未知 TNL 有兜底提示，不崩溃 |
| 地图截图版权 | 截图来自 avalon-gold-finder / 社区数据；README/NOTICE 标注来源，不单独售卖 |
| 安装包体积 | +19MB（约 40MB），可接受；若需瘦身可后改为缩略图方案 |
| Tk 抢焦点 | 全屏游戏下可能被游戏抢回；按 `F6` 重新置前即可 |
| 400 条 3 字母速记唯一性 | 已实测：原样及 I↔L 折叠后均零碰撞；数据更新后由同步脚本校验，出现碰撞则告警并依赖 L2 排序 |

## 10. 交付物

1. `client/albion_aware/map_index.py`、`map_window.py`
2. `client/data/avalon/index.json`（入库）+ `maps/*.webp`（构建期生成）
3. `tools/sync-avalon-maps`（同步/下载/校验）
4. 集成改动（config / main / overlay / tray / i18n / spec / build.ps1 / NOTICE / README）
5. 单元测试与冒烟测试
