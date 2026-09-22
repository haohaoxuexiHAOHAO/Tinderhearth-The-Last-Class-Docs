---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-22
---

# DOC-18：三条量各得一个名 —— 体质、体力条、精力条

## 目标

让「体力」这个词只指一件事：属性叫**体质**、战斗那条资源叫**体力条**（缩写仍是 `SP`）、经营那条预算叫**精力条**，全库与代码一致。

## 来源

- PRD：[`spec/prd-growth-skill-damage.md`](../prd-growth-skill-damage.md) 的 `US-002`
- 起因是**已经存在**的同名不同物，中文侧与英文侧各一处：
- 中文侧：代码仓 `data/text/zh-CN.json` 里 `hud.gauge.vigor` 的值是「体力」，而那条是**经营预算**；战斗那条显示的是裸的 `SP`。同时「体力」还是四项属性之一 —— **同名不同物已经上屏。**
- 英文侧：`stamina` 在[`数值模型`](../../design/数值模型.md)的参数路径与 `tools/simulate_week.py` 里指**经营预算**，而在代码仓 `rules/Ui/HudViewModel.cs` 的 `HudGaugeKind.Stamina` 与 `rules/Ui/HudPalette.cs` 里指**战斗那条**。
- 代码那一侧本来是**故意留白**的：`rules/Ui/HudLayout.cs` 写着「给资源起中文名是文案的事（`DOC-2` 与叙事侧），本条不顺手定」。本条是来填它。

## 依赖

无。它是 `GP-33`／`GP-34`／`GP-30`／`GP-31`／`GP-32`／`GP-35` 的**用词前提** —— 派生表要写「体质 → 体力条上限」，先按旧名写完再回头改是两次工，而只改一半会留下两种说法并存。

## 验收标准

- [ ] 三个名字各自只指一件事，互不为前缀：**体质**只指属性、**体力条**只指战斗那条、**精力条**只指经营那条。
- [ ] 设计仓非归档处的「体力」逐处按上下文判成属性、体力条或精力条。**不许批量替换** —— [WORKFLOW § 5. 命令与提交纪律](../../WORKFLOW.md)禁 shell 批量文本替换，看不到上下文就无法逐处复核。
- [ ] 大头四份改完并自查一遍：[时间与经营](../../canon/gameplay/时间与经营.md)、[`数值模型`](../../design/数值模型.md)、[玩法定位](../../canon/gameplay/玩法定位.md)、[`生产系统`](../../design/生产系统.md)。
- [ ] `archive/` 一个字不改 —— 归档件不得用今天的理由改写当时的说法（[WORKFLOW § 4. 归档](../../WORKFLOW.md)）。
- [ ] 代码仓 `data/text/zh-CN.json` 里 `hud.gauge.*` 的标签改成新名。
- [ ] `rules/Ui/HudLayout.cs` 那句「给资源起中文名是文案的事」改成指向现在定下的名字；同一处按字宽算的排版说明核一遍（「精力」与「体力」同为两字，宽度不变）。
- [ ] `rules/Ui/HudViewModel.cs` 与 `rules/Ui/HudPalette.cs` 里引用旧名的注释跟着改；**枚举值 `HudGaugeKind.Stamina`／`DailyVigor` 不改** —— 它们与 `derived.sp_*` 是别名关系，不是撞名。
- [ ] 参数表 `design/numeric-model-params.json` 里 `stamina.*` 改成 `vigor.*`，`actions.*.stamina` 与 `assignments.*.stamina` 跟着改；[`数值模型`](../../design/数值模型.md)里引这些路径的地方一并改。
- [ ] `tools/simulate_week.py` 里对应的读取与局部名跟着改（`stamina_limit`／`stamina_used`／`overstamina_days` 这一批）。
- [ ] `python tools/simulate_week.py` 全部判据成立、`--check-doc` 无分叉（改完参数键，这两个入口是唯一能证明没改漏的东西）。
- [ ] `python tools/check_docs.py` 0 项必须修复。
- [ ] 代码仓 `python tools/verify.py` 五步全绿。
- [ ] 作者实机确认：HUD 上资源标签读不读得清。

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

选「体质」而不是继续叫「体力」，是因为参数键本来就是 `vit`（vitality）—— `derived.hp_per_vit`、`derived.sp_per_vit`、`derived.def_per_vit`、`stamina.per_vit`。所以属性改名**一个参数键都不用动**，这是依据而不是语感。

### 待确认

## 验证结果

> 由 `/verify-round` 填写。**只写实际运行过的内容。**

| 命令 | 结果 | 判定 |
| --- | --- | --- |
|  |  |  |
