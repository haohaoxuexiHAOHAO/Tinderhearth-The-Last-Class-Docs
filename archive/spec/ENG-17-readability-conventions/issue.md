---
type: workdoc
status: archived
owner: project
last_verified: 2026-09-13
---

# ENG-17：代码可读性约定增补与定点重构

> **本文件已归档，只读，不得作为现行依据。** 现行编码约定见代码仓 `CONVENTIONS.md`（`ENG-4` 的产物），本轮增补的三节即在其中；现行待办见[台账](../../../spec/issues/README.md)。

## 目标

把「什么时候用 `var`、多路分派怎么写、宽构造怎么调用」从事实习惯写成 `CONVENTIONS.md` 的成文约定，并定点重构唯一一处真正伤可读性的嵌套三元。**不做全量语法糖展开。**

## 来源

- 作者 2026-09-13 实机之余读代码，反馈「语法糖与 `var` 多、可读性差」，要求进下一个需求前先做一次可读性整治。
- 分析结论（本轮）：`ENG-4`（`CONVENTIONS.md`）**并未**规定 `var` / 嵌套三元 / 目标类型 `new` / 宽构造调用；`var` 是 de-facto 习惯，且密度最高处是探针／脚手架／演示代码（`CameraProbe` 69、`HudProbe` 57、`CameraHarness` 54…），不是承重玩法逻辑。全仓唯一的**嵌套**三元在 `src/World/PlayerActor.cs` 的 `UpdateVisual`。
- 关联：`ENG-4`（本条增补它的产物 `CONVENTIONS.md`，不推翻既有条款）。

## 依赖

无。纯形状重构、行为不变，不依赖任何未完成条目。

顺带：`DOC-9` 记着 `LocalPlayerController.cs` 等处有过期的「归 `GP-2`，尚未设计」注释；本条会动 `LocalPlayerController.cs`，但**不并入** `DOC-9`（那条要等第一个真读参数表的玩法实现，边界不同）。

## 验收标准

- [x] `CONVENTIONS.md` 增补三节，每节写明依据（真实代码例子）：「局部变量与 `var`」（右侧类型显然才用 `var`，裸属性/裸方法返回类型不显然时写全）；「三元与多路分派」（**禁嵌套三元**，多路分派用 `switch` 表达式，单层三元仍可）；「构造与 `new`」（目标类型 `new` 用在类型可还原处；≥4 参或有多个同类型参数的构造用具名实参）
- [x] `PlayerActor.UpdateVisual` 的三处多路链（`action` 嵌套三元、`Sprite.Frame` 链式、`Sprite.Modulate` 链式）改为 `switch` 表达式，臂顺序照原样保序、**行为不变**（保留单层三元如 `heavy_hit/light_hit`）
- [x] 核心玩法少量**类型不显然**的 `var` 写全类型：`InputRouter` 的 `before`（`SkillGroup`，两处）、`LocalPlayerController` 的 `move`（`Vector2`，为此补 `using Godot;`）；**探针／脚手架／演示文件不动**
- [x] `LocalPlayerController.ReadCombatInput` 的 `CombatInput` 构造改具名实参（7 个参数逐个具名）
- [x] **不做**全量展开：记录、LINQ、集合表达式、表达式体成员保持不变（`CONVENTIONS.md` 已有肯定条款）；模式匹配 `switch` 与单层三元未改动——展开它们会降低可读性
- [x] 代码仓 `python tools/verify.py` 6/6（测试 **326/326**）；四图形探针无回归：`player_dev` 43/43、`hit_feedback` 73/73、`combat_debug` 11/11、`depth` 16/16
- [x] 设计仓 `python tools/check_docs.py` 0 必须修复项；`temp/` 干净、无残留探针进程

## 实现笔记

> 实现、机器验收与评审均已完成并提交（代码仓 `649dac9`、设计仓 `a48a63c`），作者确认后归档。

### 设计决策

- **模糊点**：作者反馈「`var` 与语法糖多、可读性差」，而 `ENG-4` 的 `CONVENTIONS.md` 对 `var`／嵌套三元／目标类型 `new`／宽构造**并无条款**——「可读性差」究竟是违反约定，还是约定有空白？
- **选择**：判定为**约定空白**而非违反。给 `CONVENTIONS.md` 补三节（治理 `var`、禁嵌套三元、宽构造具名实参），只定点重构证据确凿的那几处；**不做**全量 `var`／语法糖展开。
- **理由**：逐类核过真实代码——记录、LINQ、集合表达式、模式匹配、绝大多数表达式体与目标类型 `new` 都是地道用法，展开只会更啰嗦；`var` 密度最高处是探针/脚手架（`CameraProbe` 69、`HudProbe` 57…），非承重逻辑；全仓唯一的**嵌套**三元只在 `PlayerActor.UpdateVisual`。全量展开是跨 80 文件的大 diff、重构风险高、ROI 为负。

### 偏离

- **方案怎么说**：A ＝ 重构那一处嵌套三元 ＋ 相邻 `Modulate` 行。
- **实际怎么做**：`UpdateVisual` 里三处多路链（`action` 嵌套三元、`Sprite.Frame` 链式、`Sprite.Modulate` 链式）一并改 `switch`。
- **为什么**：新约定「多路分派用 switch」覆盖的是多路、不止嵌套；把其中一处留成链式三元紧挨着新 `switch` 反而不一致。三处同在一个方法、行为不变，`player_dev` 43/43 兜底。

### 权衡

- 命名 `move` 为 `Vector2` 需给 `LocalPlayerController.cs` 补 `using Godot;`（它原先只经类型推断用到 Godot 类型、没具名过）。判断：引擎层文件本就该能具名 Godot 类型，一行 `using` 换来类型就近可读，值。
- `CombatInput.None => new(0, 0, false, …)` 全默认值构造**保留位置写法**：全 `false` 没有可混淆的信息，具名反而更长。约定里写明了这个例外。

### 已定（原「待确认」）

- 三节约定的措辞与边界作者 2026-09-13 确认后归档。
- `var`「类型显然」等三节**暂不另立守卫**，与 `ENG-4` 其余风格条款（Allman、表达式体等）一样靠人工评审——「类型是否显然」是上下文判断，机械检测假阳性高、收益低。将来若要守卫另行立项。

## 验证结果

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `dotnet build` | 0 错误、0 新增警告（唯一 1 警告是 `HitSpark.cs` 既有 CS0618，非本次） | PASS |
| `python tools/verify.py` | 6/6 步；测试 **326/326**、失败 0 | PASS |
| `python tools/player_dev.py --probe` | 43/43（首跑 42/43 因窗口瞬时失焦 `focusLost=1`，复跑 43/43） | PASS |
| `python tools/hit_feedback_dev.py --probe` | 73/73（`focusLost=0`） | PASS |
| `python tools/combat_debug_dev.py --probe` | 11/11 | PASS |
| `python tools/depth_dev.py --probe` | 16/16 | PASS |
| `python tools/check_docs.py`（设计仓） | 0 必须修复项（2 条既有软上限提示，非本次） | PASS |
