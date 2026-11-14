# 采集辅助目标队列设计（Gathering Advisor）

*日期：2026-11-12 · 状态：待评审*

## 1. 背景与目标

OpenRadar 已经能被动解析资源节点（类型、tier、附魔、剩余层数、坐标），但雷达只做"画点"。
采集玩家真正要回答的问题是三个：**先采哪个、往哪走、周围安不安全**。

本设计给雷达页增加一层采集辅助能力：

1. **目标队列**：按距离、tier、附魔、剩余层数排序，告诉玩家下一个该采哪棵。
2. **导航联动**：行内显示精确方位角与距离，雷达画布上给当前目标画引导线。
3. **采集态防抓鸡**：识别"正在采集"状态，并据此提升玩家靠近告警的灵敏度。

### 非目标

- 不新增协议解析，不改 Go 后端。
- 不计算市场价值、不做跨会话持久化、不做多目标路径规划。
- **不提供玩家方位**。玩家实时坐标加密，本设计不暗示任何定位能力。
- 不替代游戏内视野，告警只作提示。

## 2. 数据来源

| 数据 | 来源 | 精度说明 |
|---|---|---|
| 节点类型 / tier / 附魔 / 层数 / 坐标 | `harvestablesHandler.harvestableList`（事件 38/40/46） | 静态节点坐标精确；活体资源按最后已知位置 |
| 本地玩家坐标 | `playersHandler.localPlayer`（Move 事件 3） | 未收到时为 0，需降级处理 |
| 节点状态变化 | 事件 46（层数减少 / 回升 / 消失） | 会丢帧、跳值，只能作为启发式信号 |
| 区域 PvP 类型 | `zonesDatabase.getPvpType` | 未知区域回落 `safe` |
| 玩家出现 / 离开 | 事件 29 `NewCharacter` / 事件 1 `Leave` | 仅代表进入可见范围，非坐标 |

字段语义提醒：`harvestable.charges` 是**附魔等级**，`harvestable.size` 是**剩余可采层数**，命名与语义相反，新代码必须按语义使用，不改字段名。

## 3. 模块划分

| 文件 | 职责 | 变更 |
|---|---|---|
| `web/scripts/utils/GatheringAdvisor.js` | 纯计算：过滤、打分、排序、采集识别 | 新增 |
| `web/scripts/drawings/GatheringDrawing.js` | 在 `uiCanvas` 画当前目标脉冲圈与引导线 | 新增 |
| `web/scripts/core/GatheringPanel.js` | 目标卡片 DOM 渲染与行悬停交互（与 `PlayerListRenderer` 同级） | 新增 |
| `internal/templates/pages/radar.gohtml` | 目标卡片、开关、排序模式控件 | 修改 |
| `web/scripts/handlers/PlayersHandler.js` | 接收采集态、扩展告警门槛、记录 `leftAt` | 修改 |
| `web/scripts/handlers/HarvestablesHandler.js` | 仅作数据源 | 不改 |
| `web/scripts/utils/RadarRenderer.js` | 在 `renderUI` 中调用引导线绘制 | 修改 |
| `web/scripts/drawings/HarvestablesDrawing.js` | 常规模式下跳过资源图层绘制 | 修改 |
| `web/scripts/core/PlayerListRenderer.js` | 玩家卡片显示离开时间 | 修改 |
| `web/scripts/utils/Utils.js` | 创建 advisor、注册绘制层、刷新节流与销毁清理 | 修改 |

约束：业务判断放在 `GatheringAdvisor`，handler 只存状态。原因是"哪棵被采"需要结合本地玩家位置，handler 没有这个上下文。

## 4. 目标队列

### 4.1 过滤

按顺序排除：

1. `size <= 0`
2. 未通过现有渲染筛选（复用 `LivingResourceFilter` 的类型/tier/附魔规则，保证列表与雷达可见点一致）
3. 与本地玩家距离 > 80（与 `removeNotInRange` 的检测半径一致）
4. 本地坐标缺失时不做距离过滤，改为全量按层级排序

### 4.2 打分

```
score = a * (1 - dist/80) + b * (tier/8) + c * (enchant/4) + d * (size/maxSize)
```

`maxSize` 取当前列表中的最大 `size`，避免写死 5。

| 模式 | a 距离 | b 层级 | c 附魔 | d 剩余 |
|---|---|---|---|---|
| 就近 `nearest` | 0.60 | 0.20 | 0.10 | 0.10 |
| 高级 `tier` | 0.15 | 0.35 | 0.35 | 0.15 |
| 效率 `efficiency` | 0.25 | 0.25 | 0.15 | 0.35 |

### 4.3 输出

`buildTargets({harvestables, playerPos, mode, maxTargets, filter, rotate})` 返回 `Target[]`，每项包含 `id / posX / posY / stringType / tier / enchant / size / distance / bearingDeg / isLiving / score`。纯函数，无 DOM、无全局状态，便于单测；`rotate` 可注入，默认使用与雷达一致的等距变换。

数量上限由 `settingGatheringMaxTargets`（1-10）控制，默认 5。

## 5. 方位与距离

### 5.1 方位角

必须在**屏幕空间**计算，与雷达渲染保持同一变换：先对 `(node - player)` 施加 `transformPoint` 的 -45° 等距旋转，再取 `atan2(dy, dx)`。

- 行内用连续角旋转箭头图标，不量化到 8 向。
- 卡片头部迷你方位盘：玩家居中、80m 为半径，所有目标按真实相对位置绘制为点，当前目标高亮。该盘与雷达点位方向一致。
- 距离显示整数米，不做区间模糊。

禁止直接使用世界坐标求方位——会与画布上的点位偏差 45°。

### 5.2 引导线

- 图层：`uiCanvas`（z-index 6），位于资源与玩家绘制之上。
- 起点：画布中心（雷达恒为玩家居中）。
- 终点：目标经同一变换后的屏幕坐标。
- 目标超出当前缩放的可见圆时，虚线止于圆边界，末端画指向箭头，不画到画布外。
- 触发：队列第一名自动高亮并画线；悬停或点击任意行时切换到该节点。
- 消失：节点被采空或离开列表后，线自动切到下一目标。

## 6. 采集态识别

`GatheringAdvisor` 对比前后两帧节点快照：

- 某节点 `size` 下降，且该节点是距离本地玩家最近的已变化节点 → 记为"刚被采集"。
- 进入采集态；持续 `GATHER_IDLE_MS`（默认 8s）无新采集事件则退出。
- 输出 `isGathering`、`lastHarvestAt`、`lastHarvestId`。

已知误差：事件 46 会丢帧或跳值，识别只能近似，不能保证每次采集都被捕获。该误差在 UI 上不体现为精确数据，只影响状态切换时机。

## 7. 采集模式告警

现有告警门槛见 `isPlayerThreat`：安全区永不告警；黄/红区仅 `faction === 255`；黑区全部告警。

新增采集模式（`settingGatherAlertMode` 开启时生效）：

| 状态 | 黄 / 红区 | 黑区 |
|---|---|---|
| 非采集 | 保持现状 | 保持现状 |
| 采集中 | 任意玩家告警（采集时无法快速上马） | 任意玩家告警 |

规则：

- 告警形态复用现有闪屏与声音，冷却沿用 `settingSoundCooldown`。
- 忽略名单依然优先，被忽略玩家不告警。
- 玩家卡片新增"出现时间 / 离开时间"标记（`just now` / `left Xs ago`），`Leave` 事件写入 `leftAt`。
- 文案区分"附近有玩家"（采集模式）与原有"Hostile"，不输出方位或距离。

## 8. 新增设置项

| Key | 类型 | 默认 | 说明 |
|---|---|---|---|
| `settingGatheringMode` | string | `gather` | `gather` / `roam`，玩法模式 |
| `settingGatheringSort` | string | `nearest` | `nearest` / `tier` / `efficiency` |
| `settingShowGatheringTargets` | bool | true | 采集模式下的目标卡片显示 |
| `settingGatheringMaxTargets` | number | 5 | 1-10 |
| `settingGatherAlertMode` | bool | false | 采集时提升告警灵敏度 |

设置沿用 `settingsSync` 的读写与跨标签页同步机制，不新增存储层。

排序设置与玩法模式必须使用不同键名：`settingGatheringMode` 只表示玩法模式，排序一律用 `settingGatheringSort`，避免互相覆盖。

### 8.1 玩法模式

| 能力 | `gather`（采集） | `roam`（常规） |
|---|---|---|
| 资源节点图层（含活体资源） | 按筛选显示 | 隐藏 |
| 目标卡片列表与迷你方位盘 | 显示 | 收起 |
| 引导线与采集态提示 | 显示 | 隐藏 |
| 玩家、地下城、迷雾、宝箱 | 保留 | 保留 |

- 常规模式只是关闭采集相关显示，雷达仍然是玩家预警工具。
- 模式切换控件放在目标卡片头部，常规模式下卡片只保留头部，保证随时能切回（整卡隐藏会导致开关不可达）。
- 资源图层在 `HarvestablesDrawing` 入口处按模式短路，聚类、数量、距离、血条随之一起隐藏；钓鱼点由 `settingFishing` 独立控制，不受模式影响。

### 8.2 资源筛选入口

资源筛选复用既有 `/resources` 页面与 `settingStatic{Fiber|Hide|Wood|Ore|Rock}Enchants`、`settingLiving*` 矩阵，不新增第二套筛选数据。

- 目标卡片头部提供"采集筛选"按钮，新标签页打开 `/resources`，避免离开雷达页导致采集态与预警中断。
- 目标队列与该矩阵共用同一套过滤逻辑，保证"列表里出现的节点，雷达上一定也能看到"。

## 9. 刷新与性能

- 队列重算挂在现有 `playerListInterval` 同级的 1s 定时器上，复用 `cleanup` 机制清理，不新增高频循环。
- 目标未变化时跳过 DOM 重绘（对 `id + size + distance 分桶` 做哈希，参照 `lastPlayerListHash` 的写法）。
- 绘制跟随现有雷达刷新帧，只画一个脉冲圈和一条虚线。

## 10. 边界处理

| 场景 | 处理 |
|---|---|
| 本地坐标缺失 | 不算距离与方位，按 tier 排序，卡片提示 `waiting for position` |
| 数据库未加载 | 队列为空，不抛错 |
| 节点列表为空 | 显示空态文案，不渲染画布元素 |
| 事件 46 丢帧造成残点 | 节点消失即剔除；层数回升视为再生重新入队 |
| 玩家离开 | 列表标记 `left`，不立即删除记录，避免告警误判 |
| 页面销毁 / HTMX 切页 | 清理定时器、事件监听与绘制回调 |
| 区域未知 | 按 `safe` 处理，与现有行为一致 |
| 切到常规模式 | 资源图层、目标列表、方位盘、引导线立即隐藏，玩家与关键点绘制不受影响 |
| 常规模式下切回采集 | 下一帧恢复资源图层，队列在 1s 内重新生成 |
| `settingGatheringSort` 值非法 | 回落到 `nearest` |

## 11. 测试

单元测试（Vitest）：

- `GatheringAdvisor`：三种模式的排序结果、距离过滤、`size<=0` 剔除、坐标缺失降级、采集态进入/退出、方位角在四个象限的屏幕空间取值。
- `PlayersHandler`：采集模式 × 区域类型 × faction 的告警矩阵；`Leave` 写入 `leftAt`；忽略名单优先。

手动验证：

- 雷达页开关与排序模式切换即时生效。
- 悬停行切换引导线；目标出视野时线止于边界。
- 采集时黄/红区任意玩家触发提示；非采集时行为不变。
- 切页后无残留定时器与画布绘制。

## 12. 后续可扩展（不在本次范围）

- 方位扇区分组、多目标路线。
- 采集会话统计与产出速率（已存在但未使用的 `stats` 骨架可作为起点）。
- 事件 59/60 抓包确认是否携带施法者信息，用于把"近似归因"升级为准确归因。

## 13. 已知限制

- 玩家坐标加密，永远无法在雷达上定位其他玩家，本设计不改变这一点。
- 玩家检测延迟与可见范围由服务器决定，告警存在滞后。
- 事件 46 不可靠，采集态与层数显示只能尽力而为。
- 资源节点坐标来自服务器下发，活体资源移动后坐标可能滞后。
