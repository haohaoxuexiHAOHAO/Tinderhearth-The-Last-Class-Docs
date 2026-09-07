---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-07
---

# GP-11：规则层统一状态载体与命中结算

## 目标

在规则层建成最小统一状态载体（硬直、无敌）与由攻击轻重决定反应的命中结算，脱离引擎即可单元测试。

## 来源

- PRD：[`prd-combat-feel-core.md`](../prd-combat-feel-core.md) 的 `US-003`、`US-004`
- SPEC：[`spec-combat-feel-core.md`](../spec-combat-feel-core.md) 的 §3.1、§4.3、§5、`StatusEffects`、`HitResolution`

## 依赖

`GP-10`——复用 `CombatFeel` 常量与 `MotorState`（无敌窗作为一个状态注册）。落实[玩法定位 · 跨系统约定](../../canon/gameplay/玩法定位.md)的「统一状态系统现在就成立」。

## 验收标准

- [ ] `rules/Combat/StatusEffects.cs`：状态条目带 `StatusKind` 与「可否解除」标志；硬直与无敌两种，A1 均不可解除；帧数每帧递减到 0 自动解除
- [ ] `rules/Combat/HitResolution.cs`：`Resolve(轻/重)` → 击退量、硬直帧、顿帧帧数、是否重击（触发震屏），取值来自 `CombatFeel`
- [ ] 单元测试：击退量与硬直帧随轻重变化、硬直刷新取新值不叠加、顿帧帧数有限且自解除、无敌与硬直的「可否解除」标志
- [ ] `rules/Combat` 不引用 Godot

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
