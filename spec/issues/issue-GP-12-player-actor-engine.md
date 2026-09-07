---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-07
---

# GP-12：引擎层主角节点与占位动画

## 目标

引擎层主角节点读输入驱动规则层状态机，表现出移动/跳/连段/闪避/冲刺，并用 samurai 占位动画。

## 来源

- PRD：[`prd-combat-feel-core.md`](../prd-combat-feel-core.md) 的 `US-001`、`US-002`、`US-003`
- SPEC：[`spec-combat-feel-core.md`](../spec-combat-feel-core.md) 的 §2.2、§5、`PlayerActor`

## 依赖

`GP-10`、`GP-11`——引擎节点驱动它们的状态机。占位精灵用 `ART-4` 已登记的下载 samurai 表。

## 验收标准

- [ ] `src/World/PlayerActor.cs`：每物理帧读 `InputRouter` 组装 `CombatInput`、推进 `MotorState`/`ComboStateMachine`、按状态给速度
- [ ] 输入全经 `InputRouter`，`src/` 无直接 `Input` 轮询（`check_input_map` 守）
- [ ] `AnimatedSprite2D` 用 `ART-4` 登记的 samurai 表建 `SpriteFrames`，映射待机/走/跳/轻攻击/重攻击/闪避；**缺帧则退占位几何并日志列出缺哪个，按超边界记账**
- [ ] 可观察：主角能左右移动、跳跃落地、打轻重连段与空中连击、闪避（有无敌表现）、按住冲刺键移动进入冲刺
- [ ] 作者实机确认：移动跳跃跟手、连段前后摇与衔接节奏顺、闪避无敌感与冲刺显式感成立

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
