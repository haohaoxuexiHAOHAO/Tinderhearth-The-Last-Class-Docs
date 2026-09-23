---
type: archive
status: archived
owner: project
last_verified: 2026-09-22
---

# DOC-18：三条量各得一个名 —— 体质、体力条、精力条

> **只读历史归档，不得作为现行依据。** 现行事实：三个名字的分工在[角色与成长 · 四项属性的作用方向](../../../canon/gameplay/角色与成长.md)，参数键在[数值模型](../../../design/数值模型.md)。

## 目标

让「体力」这个词只指一件事：属性叫**体质**、战斗那条资源叫**体力条**（缩写仍是 `SP`）、经营那条预算叫**精力条**，全库与代码一致。

## 来源

- PRD：[`prd.md`](./prd.md) 的 `US-002`
- 起因是**已经存在**的同名不同物，中文侧与英文侧各一处：
- 中文侧：代码仓 `data/text/zh-CN.json` 里 `hud.gauge.vigor` 的值是「体力」，而那条是**经营预算**；战斗那条显示的是裸的 `SP`。同时「体力」还是四项属性之一 —— **同名不同物已经上屏。**
- 英文侧：`stamina` 在[`数值模型`](../../../design/数值模型.md)的参数路径与 `tools/simulate_week.py` 里指**经营预算**，而在代码仓 `rules/Ui/HudViewModel.cs` 的 `HudGaugeKind.Stamina` 与 `rules/Ui/HudPalette.cs` 里指**战斗那条**。
- 代码那一侧本来是**故意留白**的：`rules/Ui/HudLayout.cs` 写着「给资源起中文名是文案的事（`DOC-2` 与叙事侧），本条不顺手定」。本条是来填它。

## 依赖

无。它是 `GP-33`／`GP-34`／`GP-30`／`GP-31`／`GP-32`／`GP-35` 的**用词前提** —— 派生表要写「体质 → 体力条上限」，先按旧名写完再回头改是两次工，而只改一半会留下两种说法并存。

## 验收标准

- [x] 三个名字各自只指一件事，互不为前缀：**体质**只指属性、**体力条**只指战斗那条、**精力条**只指经营那条。
- [x] 设计仓非归档处的「体力」逐处按上下文判成属性、体力条或精力条。**不许批量替换** —— [WORKFLOW § 5. 命令与提交纪律](../../../WORKFLOW.md)禁 shell 批量文本替换，看不到上下文就无法逐处复核。
- [x] 大头四份改完并自查一遍：[时间与经营](../../../canon/gameplay/时间与经营.md)、[`数值模型`](../../../design/数值模型.md)、[玩法定位](../../../canon/gameplay/玩法定位.md)、[`生产系统`](../../../design/生产系统.md)。
- [x] `archive/` 一个字不改 —— 归档件不得用今天的理由改写当时的说法（[WORKFLOW § 4. 归档](../../../WORKFLOW.md)）。
- [x] 代码仓 `data/text/zh-CN.json` 里 `hud.gauge.*` 的标签改成新名。
- [x] `rules/Ui/HudLayout.cs` 那句「给资源起中文名是文案的事」改成指向现在定下的名字；同一处按字宽算的排版说明核一遍（「精力」与「体力」同为两字，宽度不变）。
- [x] `rules/Ui/HudViewModel.cs` 与 `rules/Ui/HudPalette.cs` 里引用旧名的注释跟着改；**枚举值 `HudGaugeKind.Stamina`／`DailyVigor` 不改** —— 它们与 `derived.sp_*` 是别名关系，不是撞名。
- [x] 参数表 `design/numeric-model-params.json` 里 `stamina.*` 改成 `vigor.*`，`actions.*.stamina` 与 `assignments.*.stamina` 跟着改；[`数值模型`](../../../design/数值模型.md)里引这些路径的地方一并改。
- [x] `tools/simulate_week.py` 里对应的读取与局部名跟着改（`stamina_limit`／`stamina_used`／`overstamina_days` 这一批）。
- [x] `python tools/simulate_week.py` 全部判据成立、`--check-doc` 无分叉（改完参数键，这两个入口是唯一能证明没改漏的东西）。
- [x] `python tools/check_docs.py` 0 项必须修复。
- [x] 代码仓 `python tools/verify.py` 五步全绿。
**不在本条验收范围**：HUD 标签在实机上读不读得清，是作者在 Godot 里看的事（[ADR-0009](../../../decisions/ADR-0009-编辑器主导的开发模式.md) 的分工），与本条要交付的「三条量各只有一个名」无关。本条的完成边界是文档、参数表与文本键三处一致，那三样都已验过。

## 实现笔记

> 由 `/note-it` 在实现和评审之后填写。

### 设计决策

- **模糊点**：`hud.gauge.sp` 的显示值该写「体力」还是「体力条」。参数键与正典的缩写都是 `SP`，而「条」是 UI 上那根条的说法。
- **选择**：HUD 标签写**「体力」**与**「精力」**，散文里需要强调它是一条资源时写「体力条」「精力条」。
- **理由**：标签列按两个全宽汉字算宽度（`rules/Ui/HudLayout.cs`），三个字要么换算要么截断；而三个词互不为前缀这条保证在两个字上就已经成立 —— 属性叫体质，所以「体力」不会被误读成属性。

### 偏离

- **方案怎么说**：条目只要求改 `stamina.*` 这一节的键。
- **实际怎么做**：顺带把 `actions.*.stamina` 与 `assignments.*.stamina` 两批子键、以及 `tools/simulate_week.py` 里的字段、函数名与输出表头一起改了。
- **为什么**：那些子键读的就是同一条量。留着它们叫 `stamina`、而上限那节叫 `vigor`，等于把撞名从「两个系统之间」搬到「同一份参数表内部」，更难发现。

### 权衡

选「体质」而不是继续叫「体力」，是因为参数键本来就是 `vit`（vitality）—— `derived.hp_per_vit`、`derived.sp_per_vit`、`derived.def_per_vit`、`vigor.per_vit`。所以属性改名**一个参数键都不用动**，这是依据而不是语感。

`HudGaugeKind.Stamina` 与 `derived.sp_*` 保留两个英文名，没有强行统一：它们指同一件事，属别名；统一要动公式引用一大片而收益为零。真正的撞名只有 `stamina` 同时指两条资源那一处，已经消掉。

### 待确认

标签读不读得清只能实机看。按 [ADR-0009](../../../decisions/ADR-0009-编辑器主导的开发模式.md) 的分工归作者，本条不判。

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `python tools/check_docs.py` | 104 份文档／0 项必须修复／0 条提示 | 通过 |
| `python tools/simulate_week.py` | 16/16 条通过／0 条不成立；读了 84 个参数路径，核了 13 处正文抄的算出来的量 | 通过 |
| `python tools/simulate_week.py --check-doc` | 认出 42 个参数路径全部对得上，核了 16 处路径旁的数字，无分叉 | 通过 |
| 代码仓 `python tools/verify.py` | 5/5 步通过；测试 347／347，构建 0 错 0 警，导出泄漏 0 条 | 通过 |
| 全库搜 `stamina` | 只剩刻意写的说明（`数值模型` 那句「两处都不用了」与 PRD 的需求正文） | 通过 |
