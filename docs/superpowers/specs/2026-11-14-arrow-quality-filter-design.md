# 资源行带杆箭头 + 层级×附魔品质筛选 设计

日期：2026-11-14
状态：已确认（用户选择「带杆箭头」与「T1~T8 × 附魔 0~4 矩阵」）
前置：2026-11-14-danger-zone-merged-overlay-design.md（资源行排版延续该规格）

## 1. 目标

1. 资源行右侧方向指示由纯三角形改为「带杆箭头」，方向辨识度更高。
2. 采集筛选支持按「层级 × 附魔」精确选择（如只要 5.1/5.2/5.3/5.4/6.0/6.1…），替换现有的 tier_min~tier_max 区间。

## 2. 带杆箭头

- Canvas 尺寸 `ARROW_SIZE` 10 → 12；行内容可用宽度仍为 66px。
- 绘制：1px 宽短杆（线段）+ 实心三角头，整体按 `bearing_deg` 连续角度旋转；杆从尾部指向中点，三角头从中点指向尖端。
- `arrow_points(angle_deg, size)` 重命名/扩展为返回 `(杆线段坐标, 三角头坐标)`；`bearing_deg` 为 None 或非有限时仍按 0° 处理（与现行为一致）。
- 无法定位（bearing None）仍画 10px 内小圆点。
- 颜色沿用 `RESOURCE_ARROW`。
- 宽度预算：原最宽行 63px（LG/RK）+ 2px = 65px ≤ 66px；真实字体宽度测试上限保持 66。

## 3. 品质筛选（UI）

资源种类改为页签（Log/Rock/Fiber/Hide/Ore 五个），每种资源独立配置品质：

- 每个页签内：
  - 顶部「显示该资源」复选框 → `gather.kinds`；取消勾选后整类资源不显示，但页签内的品质勾选保留。
  - 品质矩阵：表头横向 T1~T8 共 8 列；左侧纵向附魔 0~4 共 5 行；40 个复选框，文本 `tier.enchant`。
  - 矩阵下方「全选 / 清空」按钮，只作用于当前页签。
- 全局控件（活体、排序、最多显示）留在页签外，保持原样。
- 校验：至少启用一种资源（`gather.settings.no_kinds`）；每个已启用种类至少选一种品质（`gather.settings.no_qualities`，错误信息带种类名）。

## 4. 配置与迁移

- `gather.kinds`：启用种类列表（沿用）。
- `gather.qualities`：对象，键为种类，值为 `"tier.enchant"` 字符串数组（如 `"5.1"`）；保存全部 5 个种类，便于禁用后保留选择。
- 默认：5 个种类均启用，每种 40 项全选。
- 删除默认键 `gather.tier_min` / `gather.tier_max`。
- `CONFIG_VERSION` 5 → 6；迁移：
  - `legacy < 5` 且存在旧键：先展开为扁平字符串数组（`[tier_min..tier_max] × [0..4]`，不放宽原有范围），删除旧键。
  - `legacy < 6` 且 qualities 是数组：转为按种类字典；已启用种类沿用该数组，未启用种类填 40 项默认。
- 容错：某键缺失或非法 → 该种类回退 40 项；扁平数组仍被接受（应用到全部种类）。

## 5. 筛选判定（gather_targets.py）

- `GatherFilter.qualities: dict[str, frozenset[tuple[int, int]]]`（配置层负责字符串↔元组转换）。
- `kinds` 决定哪些种类参与；`select_targets` 先判 `node.kind`，再判 `(node.tier, node.enchant or 0) in qualities.get(node.kind, frozenset())`。
- `to_dict()` 输出 5 个种类的字符串数组；`is_default()` 与默认值全等判断。

## 6. 改动文件

| 文件 | 改动 |
| --- | --- |
| gather_targets.py | GatherFilter.qualities 按种类字典、from_config、to_dict、select_targets 判定 |
| gather_settings_window.py | 资源种类页签、每页签品质矩阵、启用开关、全选/清空、validate、_collect/_reset |
| config.py | DEFAULT_CONFIG、CONFIG_VERSION=6、迁移 |
| overlay.py | ARROW_SIZE=12、带杆箭头绘制 |
| lang/zh-CN.json、en.json | 新增 qualities/all/clear/no_qualities/show_kind；删除 tier/tier_order |
| tests | test_gather_targets、test_gather_settings_window、test_config、test_overlay 对应更新 |

## 7. 测试要点

- 箭头：12px 带杆坐标合法性（头在杆前方）、0°/90°/None 角度、资源行真实字体宽度 ≤66px。
- 筛选：同一 tier/enchant 在 Fiber 选中时显示、在 Log 未选中时不显示；禁用种类不显示；某键缺失回退全选；`to_dict`/`from_config` 回环。
- 迁移：v4 配置 tier_min=5,tier_max=6 → 10 项品质；v5 扁平数组且只启用 Fiber → Fiber 保留旧值、其它种类 40 项；旧键删除。
- 设置窗：清空某已启用种类的品质后保存报错；全选回默认；勾选矩阵保存后立即生效（invalidate_resources 由 main 既有逻辑保证）。

## 8. 边界与已知限制

- 迷雾/红黑区玩家行与本次改动无关。
- 五个页签各 40 项矩阵，设置窗变高变宽；可接受（低频操作）。
- 老配置若 tier_min>tier_max（历史上层已交换），迁移前仍按 min/max 归一后展开。
- `show_living` 仍为全局开关，不按页签区分。
