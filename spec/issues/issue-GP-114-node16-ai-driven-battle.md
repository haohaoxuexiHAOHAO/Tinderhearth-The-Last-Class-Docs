---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-28
---

# GP-114：那一场的机制侧 —— AI 驱动、自动起身、固定短关

## 目标

学生那一场真的打起来，而且全员倒下在物理上不可能发生。

## 来源

PRD：`spec/prd-richness-and-feel.md` 的 `US-014` 机制那一半。取舍在 [ADR-0024](../../decisions/ADR-0024-学生那条战线改成一场真打.md)。

**可行性已核过代码，不是推断**：`rules/Foundation/Actors/ActorControl.cs` 里 `ActorControllerKind` 的 `Ai` 取值已经占位，`ActorControllerRegistry` 的 `Assign` 注释写着「可替换是本类存在的全部理由」，且明确写了「任何『这个角色是不是主角』的判断都不得用来决定它由谁驱动」。`rules/Combat/ICombatController.cs` 现在有两个实现（`src/Platform/LocalPlayerController.cs` 与 `src/Platform/StationaryController.cs`），**AI 是第三个实现，不是一处改造**。摄影机换跟随目标走 `rules/Ui/CameraRig.cs` 与 `src/World/GameCamera.cs`。

## 依赖

`NR-39`（叙事侧先定）、`GP-36`（队友 AI —— 没有它这一场打不起来）、`GP-18`（状态载体扩容 —— 自动起身与临时增益都落在它上面）。

**分工**（[ADR-0009](../../decisions/ADR-0009-编辑器主导的开发模式.md)）：那一关的场景、站位与摄影机机位由作者在 Godot 里搭；驱动、起身规则与那一场的边界由代理写，交界面是 `[Export]`。

## 验收标准

- [ ] 学生在这一场由 `Ai` 那一档驱动，走 `ICombatController` 已有的抽象，不新开一条控制路径
- [ ] 反证：把这一场里全部学生打到零血，没有一个进入倒下终态
- [ ] 反证：那次自动起身不消耗救起额度 —— 在别的关卡里救起仍然每人一次
- [ ] 那条自动起身**只对这一关成立**，不推广到别处（写成关卡级的一个声明，不是全局规则）
- [ ] 这一场是固定手工短关，**不走片段拼装**，且写明为什么
- [ ] 玩家在这一场没有可操作角色，输入只接暂停与跳过两样
- [ ] 屏数、时长上限与临时增益幅度登记进[数值模型](../../design/数值模型.md)的尚未给值表，本条不给值
- [ ] 失败路径：中途退出游戏，靠临时续玩点恢复到那一关入口
- [ ] **作者实机确认**：一场玩家不操作的战斗看不看得下去、摄影机跟谁 —— 这条没有机器判据（ADR-0024 写明了）
- [ ] `python tools/check_docs.py` 0 FAIL

## 实现笔记

> 由 `/note-it` 在实现和评审之后填写。

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

> 由 `/verify-round` 填写。**只写实际运行过的内容。**

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
