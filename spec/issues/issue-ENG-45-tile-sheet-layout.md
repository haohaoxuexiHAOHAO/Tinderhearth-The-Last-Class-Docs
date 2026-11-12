---
type: workdoc
status: draft
owner: project
last_verified: 2026-11-12
---

# ENG-45：图块表进代码仓，排法只写在一处

## 目标

作者的图块表在代码仓里；每一套、每一块整块、崖那一片每一格在表上的位置与它是哪一种块，只写在代码仓一处，样板生成器读它出样板。

## 来源

- PRD：[`spec/prd-outdoor-tile-sheet.md`](../prd-outdoor-tile-sheet.md) 的 `US-001` 前三格，`FR-10`。

## 依赖

- `GP-173`：背包那一份收尾之前不改代码，理由在那份需求的「概述」里。
- 作者：开工时把工作区根的 `total_texture.png` 放进代码仓 `res://assets/self-drawn/tiles/outdoor_summer.png`，在 Godot 里导入一次。

## 验收标准

- [ ] 可核对：代码仓 `res://assets/self-drawn/tiles/outdoor_summer.png` 与工作区根 `total_texture.png` 逐像素一样。
- [ ] 可核对：排法只在代码仓 `rules/Foundation/Terrain/` 下一处：每一套的位置、每一块整块的位置与大小、崖那一片每一格的位置与种类，以及四角编码到一套里哪一格的那张映射表；两个仓里搜不到第二份。
- [ ] 可测试（规则层单测）：排法自己说得通：各块不重叠、都在图内、总宽等于图块表的宽，崖那一片每一格都有种类。
- [ ] 可核对：样板生成器进代码仓 `tools/`，从这份排法读位置；重出的 1:1 底稿与工作区 `art-source/self-material/tiles-template/outdoor-sheet-template.png` 逐像素一样，放大带说明那张照旧出得来；工作区 `temp/outdoor_sheet_guide.py` 删掉。
- [ ] 可核对：代码仓 verify 全过。

## 实现笔记

### 设计决策

- **排法写在代码里，不放进检查器**：理由在那份需求「技术考虑」里「排法写在代码里，作者不在检查器里填坐标」那一条。

### 偏离

（实现后填写）

### 权衡

（实现后填写）

### 待确认

（实现后填写）

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
