---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-18
---

# GP-14：训练房（作者搭场景，代理接线）

## 目标

搭出一个能玩的侧视训练房，把 A1 的各部件摆在一起，由作者实机确认整套手感。

**它同时是新分工（[ADR-0009](../../decisions/ADR-0009-编辑器主导的开发模式.md)）的第一次实跑，所以先做它再推广到其余场景（`ENG-21`）。**

## 分工

| 谁 | 做什么 |
| --- | --- |
| 作者 | 在 Godot 里搭节点树：地面（48px 纵深带的带状地形）、主角、碰撞区域、两个沙包（我方与敌方各一）、障碍物、相机；在检查器里填参数与摆位 |
| 代理 | 把 `TrainingRoom.cs` 改成读作者搭好的节点与导出参数，不再自己 `AddChild`；缺子节点时报错说清缺谁，不自己补建 |

两个沙包分属两个阵营，这样 `GP-17` 的阵营门控阻挡两个方向都测得到。

## 来源

- PRD：[`A1/prd.md`](../../archive/spec/A1-combat-feel-core/prd.md) 的 `US-006`（**历史背景·非依据**）
- SPEC：[`A1/spec.md`](../../archive/spec/A1-combat-feel-core/spec.md) 的 §2、§8（**历史背景·非依据**）
- 纵深三条（**历史背景·非依据**）：[`GP-15`](../../archive/spec/A1-combat-feel-core/issue-GP-15-depth-axis-motion.md)、[`GP-16`](../../archive/spec/A1-combat-feel-core/issue-GP-16-depth-hit-tolerance.md)、[`ENG-15`](../../archive/spec/A1-combat-feel-core/issue-ENG-15-depth-sorting-shadow.md)
- 工具：[`ENG-6`](../../archive/spec/A1-combat-feel-core/issue-ENG-6-frame-tuning-tools.md) 的 `CombatDebugOverlay`（**历史背景·非依据**）

## 依赖

`ENG-20`（手感数值要先能在检查器里调，否则作者确认手感时改不动数）。前序玩法条目 `GP-10` ～ `GP-17`、`ENG-6`、`ENG-15` 均已完成。

## 验收标准

- [ ] 场景在 Godot 编辑器里**打开就看得见**：节点树有地形、主角、两个沙包、障碍物、相机，不是一个空 `Node2D`
- [ ] **三轴都能用**：横向移动与奔跑、跳跃、`W`/`S` 走纵深；角色按纵深偏移绘制并排序、影子留在地面
- [ ] **命中是纵深感知的**：同一横向距离，纵深对齐打得到、错开一排打空
- [ ] **阻挡两个方向都成立**：撞我方沙包不穿过，撞敌方沙包不穿过；纵深方向走进去也拦得住
- [ ] 主路径走通：待机 → 轻击三段（各段独立动画与判定框）→ 命中产生硬直与顿帧 → 重击单招 → 闪避（闪步）进无敌窗 → 回待机
- [ ] 边界成立：连段超时回落、打空不续段、无方向输入时闪避取向、震屏关掉后零位移、空中连击落地打断
- [ ] `CombatDebugOverlay` 可开关（`V`／`P`／`.`），帧步进不改变结算
- [ ] 代码仓 `python tools/verify.py` 五步全绿
- [ ] **`ENG-16` 并入**：摆满编（15 敌 + 5 角色 + 互动物件）看 48px 带够不够 —— 排位读不读得清、打起来挤不挤。结论若是不够，回改 `DepthBand.WidthWorldPx` 并连同正典那笔几何账一起重算（**不许凭手感改数**）
- [ ] 作者实机确认：移动与跳跃、轻击三段与重击、闪避与奔跑、四件套「打得实」、纵深挪步与排位可读、帧步进复核；1080p 与 1440p 各看一遍字与像素清晰

## 口径提醒

三处容易记错的：轻击是**三段各有独立动画与判定框**，重击是**单招**（`HeavyChainLength=1`），闪避是**闪步**、移动加速档叫**奔跑**（`MotorPhase.Run`，设计文档里的「冲刺」指同一件事）。
