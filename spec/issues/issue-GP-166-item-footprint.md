---
type: workdoc
status: archived
owner: project
last_verified: 2026-11-06
---

# GP-166：物品声明占地，图标尺寸与占地对不上时启动就报

## 目标

每件物品的定义写明它在背包网格里占几格宽、几格高；占地写错载入被拒，图标尺寸不等于占地乘基础单位时启动就一次全报。

## 来源

- PRD：[`spec/prd-grid-bag.md`](../prd-grid-bag.md) 的 `US-001`。

## 依赖

无。

## 验收标准

- [x] 可测试：物品定义多一格占地，宽与高各是至少 1 的整数格；缺这一格、缺宽或高、或者不是正整数，载入被拒并说清是哪一件、哪一格。占地在代码仓 `rules/Progression/ItemFootprint.cs`，挂在 `rules/Progression/ItemDefinition.cs` 上；用例在 `tests/Progression/ItemCatalogTests.cs`：缺 `footprint`、缺宽、缺高各在解析时报错，写成 0、负数、小数、字符串或 `null` 各被拒，报错里有那一份的路径与那一格的名字。
- [x] 可核对：代码仓 `data/items/` 下现有的每一件都补上占地 1×1。
- [x] 可测试：图标的宽高不等于占地乘基础单位时，启动时一次全报，一行一件，写清应有多大、实际多大；变异那一张同样核。判在代码仓 `rules/Economy/ItemIconCheck.cs`，每一张多大由 `src/UI/ItemIcon.cs` 从贴图读出来交过去；用例在 `tests/Economy/ItemIconCheckTests.cs`：一格的东西配了 32×32、2×2 的宝石配了 16×16、变异那一张不对、两张都不对各一条。
- [x] 可核对：[`物品系统`](../../design/物品系统.md)那张字段表有占地那一行，图标那一格写的是「照占地的大小画」。
- [x] 可核对：代码仓 `python tools/verify.py` 全绿；设计仓 `python tools/check_docs.py` 0 FAIL。

## 实现笔记

### 设计决策

- **占地写成一个小对象**：`"footprint": { "width": 1, "height": 1 }`。宽与高是同一件事的两半，放在一起读得出来，报错路径也写成 `footprint.width` 这样一眼看得出是哪一格。两格都是 `required`，缺了在解析时报错，不拿 0 或 1 填上。
- **核尺寸判在规则层，引擎层只量**：图标资源把每一张贴图自己报的宽高交过来，没配的那一张交 `null`。从一张大图上框出来的那种（AtlasTexture）报的是框的宽高加上 Margin，写在 `src/UI/ItemIcon.cs` 的注释里。
- **一件物品报一行**：图标与变异那一张都不对时写在同一行，先写占地与应当多大，再列每一张实际多大。没配的那一张已经报过缺，不再核它多大；无品质的东西配了变异那一张只报「用不上」。
- **「图标应当多大」只有一处**：`ItemIconCheck.IconSizeFor`，占地的宽高各乘基础单位。背包页画那一块时读同一处，不另算。
- **经营那一侧读界面那一侧的排版单位**：基础单位与像素尺寸那个类型都在 `Rules.UI`（代码仓 `rules/UI/UIMetrics.cs`）。`Rules.UI` 不读经营与物品那两侧，所以不成圈。
- **两处注释跟着正典**：代码仓 `rules/UI/UIMetrics.cs` 里基础单位那一句写的是背包网格的一格是它、物品图标是占地乘它；物品定义里堆上限那一句写的是「一堆装多少件」。

### 偏离

无。

### 权衡

- **没选拆成两个平的键**（`footprintWidth`、`footprintHeight`）：一样读得出来，但两个键分开之后可以只写一个，而缺的那一个要另写一条规则才报得出来；放在一个对象里，`required` 一次管住两格。

### 待确认

无。

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `python tools/verify.py`（代码仓） | 7/7 步通过：测试报告 1018 条、静态数出 1018 条，失败 0；导出的 exe 启动跑到内容载入完成，错误 0 条 | 通过 |
| 故意让核尺寸那一步不读占地、一律按一格算，再跑 `dotnet run --project tests --no-build -- -class 'Tinderhearth.Rules.Tests.Economy.ItemIconCheckTests'`（代码仓） | 「大东西的图标正好是它那一块那么大时没有问题」「大东西画成一格那么大_报的是它那一块的大小」两条失败；已改回 | 通过（判得到） |
| `python tools/check_docs.py`（设计仓） | 0 项必须修复、0 条提示 | 通过 |
| 代码仓提交 | `b9e6e7a` | —— |
