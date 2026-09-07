---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-04
---

# GP-10：规则层主角运动学与轻重连段状态机

## 目标

在规则层建成主角的运动学与轻重连段状态机，以及集中的手感可调常量，脱离引擎即可单元测试。

## 来源

- PRD：[`prd-combat-feel-core.md`](../prd-combat-feel-core.md) 的 `US-001`、`US-002`、`US-003`（运动学部分）
- SPEC：[`spec-combat-feel-core.md`](../spec-combat-feel-core.md) 的 §3、§4.2、§5、`CombatFeel`

## 依赖

无——本 PRD 起点。实现 `GP-1` 已定义的战斗结构（`GP-1` 已归档，不阻塞）。手感数值属 `GP-6`、持在代码可调，**不消费 `GP-2`**。

## 验收标准

- [ ] `rules/Combat/CombatFeel.cs`：前后摇、无敌窗、顿帧时长、击退量、跳跃初速/重力、冲刺速度等为 `const`，量纲写入名，无浮点魔法数散落各处
- [ ] `rules/Combat/MotorState.cs`：移动/跳/落地/闪避/冲刺逐帧推进；闪避方向取按下瞬间当帧值（`GP-9`），不引入缓冲窗口
- [ ] `rules/Combat/ComboStateMachine.cs`：轻、重连段的段—相（Startup/Active/Recovery）；衔接窗内续接下一段、窗外回落待机；空中连段落地即打断
- [ ] 单元测试覆盖：某段第 X 帧进入 Active、无敌窗起止帧、衔接窗内/外的续接与回落、空中落地打断、闪避方向取当帧
- [ ] `rules/Combat` 不引用 Godot（编译层保证，`verify.py` 结构检查）
- [ ] 不做取消与派生（`GP-4` 不在本切片）

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
