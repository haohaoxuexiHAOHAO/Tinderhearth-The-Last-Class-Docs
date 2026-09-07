---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-07
---

# GP-14：训练房场景与端到端

## 目标

组装可运行的侧视训练房场景，走通端到端并由作者实机确认整套手感。

## 来源

- PRD：[`prd-combat-feel-core.md`](../prd-combat-feel-core.md) 的 `US-006`
- SPEC：[`spec-combat-feel-core.md`](../spec-combat-feel-core.md) 的 §2、§8

## 依赖

`GP-10`、`GP-11`、`GP-12`、`GP-13`、`ENG-6`——端到端收尾，依赖全部前序条目。

## 验收标准

- [ ] `scenes/TrainingRoom.tscn`：侧视场景，含 `InputRouter`、`GameCamera(SideView)` 跟随主角、地形、`PlayerActor`、`TrainingDummy`、`CombatDebugOverlay`
- [ ] **不改动** `scenes/Main.tscn` 及其启动探针链（那是 `UI-1` 验收执行体，`verify.py` 跑产物与专项守卫都读它）
- [ ] 自动化端到端走主路径：待机 → 连段各段 → 命中产生硬直与顿帧 → 闪避进无敌窗 → 回待机；条数与 `verify.py` 静态计数一致
- [ ] 覆盖失败/边界：连段超时回落、无方向输入时闪避取向、屏幕震动关零位移、空中连击落地打断
- [ ] 代码仓 `python tools/verify.py` 全绿（构建/测试/导出/跑产物），`temp/` 干净
- [ ] 本轮手感参数快照与帧步进截图存证落 `logs/`
- [ ] 作者实机确认（PRD `US-006` 清单）：移动跳跃/连段/闪避冲刺/四件套「打得实」/帧步进复核；1080p 与 1440p 各看一遍字与像素清晰

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
