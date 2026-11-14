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

## 3. 品质筛选矩阵（UI）

- 设置窗中「层级范围」一行替换为「品质」矩阵：
  - 表头横向 T1~T8 共 8 列；左侧纵向附魔 0~4 共 5 行；40 个复选框。
  - 复选框显示为层级缩写（如 `5.1`），悬停无需提示；列头用 i18n 短标签（T1…T8），行头为数字 0~4。
  - 底部「全选 / 清空」两个按钮；清空后保存报错 `gather.settings.no_qualities`（至少选 1 项）。
- 其余控件（种类、活体、排序、数量）不动；窗口高度随矩阵自然增高。

## 4. 配置与迁移

- 新键 `gather.qualities`：字符串数组，元素 `"tier.enchant"`（如 `"5.1"`、`"6.0"`）；默认 40 项全选。
- 删除默认键 `gather.tier_min` / `gather.tier_max`。
- `CONFIG_VERSION` 4 → 5；迁移：`legacy < 5` 且存在旧键时，展开 `[tier_min..tier_max] × [0..4]` 为 qualities（不放宽用户原有范围），随后删除旧键。
- 非法值容错（quality 串不是 `t.e` 或超界）：丢弃该元素；全部非法/为空时回退全选默认。

## 5. 筛选判定（gather_targets.py）

- `GatherFilter` 字段 `tier_min/tier_max` → `qualities: frozenset[tuple[int, int]]`（内部用元组集合，配置层负责字符串↔元组转换）。
- `select_targets` 中层级区间判断替换为 `(node.tier, node.enchant) in filters.qualities`。
- `to_dict()` 输出 qualities 字符串列表；`is_default()` 与默认 40 项全等判断。

## 6. 改动文件

| 文件 | 改动 |
| --- | --- |
| gather_targets.py | GatherFilter 字段、from_config、to_dict、select_targets 判定 |
| gather_settings_window.py | 矩阵 UI、全选/清空、validate、_collect/_reset |
| config.py | DEFAULT_CONFIG、CONFIG_VERSION=5、迁移 |
| overlay.py | ARROW_SIZE=12、带杆箭头绘制 |
| lang/zh-CN.json、en.json | 新增 qualities/all/clear/no_qualities；删除 tier/tier_order |
| tests | test_gather_targets、test_gather_settings_window、test_config、test_overlay 对应更新 |

## 7. 测试要点

- 箭头：12px 带杆坐标合法性（头在杆前方）、0°/90°/None 角度、资源行真实字体宽度 ≤66px。
- 筛选：命中 `(5,1)` 显示；`(6,0)` 在选中 `6.0` 时显示；未选中 `(5,0)` 不显示；空集合回退默认；`to_dict`/`from_config` 回环。
- 迁移：v4 配置 tier_min=5,tier_max=6 → qualities 含 5.0~6.4 全部 10 项，旧键删除。
- 设置窗：清空后保存报错；全选回默认；勾选矩阵保存后立即生效（invalidate_resources 由 main 既有逻辑保证）。

## 8. 边界与已知限制

- 迷雾/红黑区玩家行与本次改动无关。
- 40 项矩阵使设置窗明显变高；可接受（低频操作）。
- 老配置若 tier_min>tier_max（历史上层已交换），迁移前仍按 min/max 归一后展开。
