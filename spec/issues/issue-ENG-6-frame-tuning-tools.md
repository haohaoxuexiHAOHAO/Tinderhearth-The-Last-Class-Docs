---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-04
---

# ENG-6：帧级调优工具选型与最小自建

## 目标

给出现成帧调优候选在 Godot 4.7.2 的评估结论，并自建补缺的最小帧步进与判定框可视化。

## 来源

- PRD：[`prd-combat-feel-core.md`](../prd-combat-feel-core.md) 的 `US-005`
- SPEC：[`spec-combat-feel-core.md`](../spec-combat-feel-core.md) 的 §2.2、§10.2、`CombatDebugOverlay`
- 台账既有条目 `ENG-6`，随 `combat-feel-core` PRD 激活

## 依赖

`GP-12`——要有能动的战斗才验得了工具（可与 `GP-13` 并行建）。依赖 `ENG-2`（已完成）。

## 验收标准

- [ ] 三候选（引擎自带碰撞框可视化 / `animated-shape-2d` / `Fray`）在 4.7.2 + `net10.0` 实测结论：各能做什么、为何自建补哪一层，结论写回本条与台账备注
- [ ] `src/World/CombatDebugOverlay.cs`：帧步进（暂停 / 单帧前进）+ 判定框/受击框叠层，默认关、仅调试开
- [ ] 帧步进不改变结算结果（步进与实时跑同一份规则层状态机，可测）
- [ ] 顿帧实现方式（`Engine.TimeScale` vs 手动 hitstop）实测选定并记录理由
- [ ] 引擎内帧级/场景测试框架是否采用 GdUnit4Net 给出结论
- [ ] 作者实机确认：用这套工具能把 `US-001`~`US-004` 的手感调到位

## 实现笔记

> 由 `/note-it` 在实现和评审之后填写。四类都要过一遍，某类没有就写「无」并简要说明。

### 设计决策

- **模糊点**：
- **选择**：
- **理由**：

### 偏离

- **方案怎么说**：
- **实际怎么做**：
- **为什么**：

### 权衡

### 待确认

## 验证结果

> 由 `/verify-round` 填写。只写实际运行过的内容。

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
