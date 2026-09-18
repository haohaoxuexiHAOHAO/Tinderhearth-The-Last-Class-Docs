---
type: archive
status: archived
owner: project
last_verified: 2026-09-18
---

# ENG-6：帧级调优工具选型与最小自建

> **只读历史归档，不得作为现行依据。** 随 A1 归档；文中的验收手段（图形探针与守卫）已全部删除。
> `CombatDebugOverlay` 本体仍在代码仓 `src/World/`。现行事实见[待办台账](../../../spec/issues/README.md)。

## 目标

给出现成帧调优候选在 Godot 4.7.2 的评估结论，并自建补缺的最小帧步进与判定框可视化。

## 来源

- PRD：[`A1/prd.md`](./prd.md) 的 `US-005`（**历史背景·非依据**，2026-09-18 归档）
- SPEC：[`A1/spec.md`](./spec.md) 的 §2.2、§10.2、`CombatDebugOverlay`（**历史背景·非依据**）
- 台账既有条目 `ENG-6`，随 `combat-feel-core` PRD 激活

## 依赖

`GP-12`——要有能动的战斗才验得了工具（可与 `GP-13` 并行建）。依赖 `ENG-2`（已完成）。

## 验收标准

- [x] 三候选结论：**自建**。引擎自带「Visible Collision Shapes」实测是**全局画一切碰撞形状**，给不出本工具要的语义（判定框只在 Active 帧有几何、要分判定/受击、还要帧步进）；`animated-shape-2d`／`Fray` 是 GDScript 插件、`SPEC` §10.2 已记其在 4.7.2+`net10.0` 未验且需互操作 —— **本轮未安装实测**（一个 ~180 行的世界空间 `Node2D` 就覆盖需求，帧步进那半还是这两个插件都不做的，为默认关的调试叠层引入 GDScript 依赖不划算）。见下「设计决策／偏离」
- [x] `src/World/CombatDebugOverlay.cs`：帧步进（暂停 / 单帧前进）+ 判定框/受击框叠层，默认关、仅调试开
- [x] 帧步进不改变结算结果（步进与实时跑同一份 `AdvanceCombat`）：探针 `paused-freezes-combat` + `step-advances-exactly-one` + `step-runs-full-resolution`（单步命中木桩，硬直帧 ≙ 规则层）
- [x] 顿帧实现：**手动 hitstop**（`rules/Combat/HitstopTimer` + 引擎层薄包装 `Hitstop`，纯计数、不碰 `Engine.TimeScale`）。理由：`TimeScale=0` 会波及 `InputRouter`／动画树等全局（`SPEC` §10.2），手动只冻结战斗推进与相机、可测。**GP-11/GP-13 已落地，本条据实记录**；帧步进复用同一「当帧不推进」介入点
- [x] 引擎内帧级/场景测试框架：**不采用 GdUnit4Net**。踩坑记录 30 已实测 `dotnet test`＋GdUnit4/xunit.v3 在 `net10.0` 跑不通；引擎层验证走既有**图形探针**模式（python runner ＋ `[标签] PASS/FAIL` 日志契约），本条的 `CombatDebugDev`＋`combat_debug_dev.py` 即又一实例
- [x] 作者实机确认：**2026-09-12 实机看过，未发现问题**（交互命令 `python tools/run_local_check.py combat_debug_dev.py`，`V` 开叠层、`P` 暂停、`.` 单步）。工具本身可用；**它的第一份产出就是抓到一个真缺陷** —— 主角受击框比画面高 4px，已立项 [`GP-19`](./issue-GP-19-hurtbox-per-actor.md)。手感数值的逐帧收敛仍归 `GP-6`，那不是本条的事

## 实现笔记（2026-09-12）

### 设计决策

- **帧步进走「场景 gate `AdvanceCombat`」，不用 `Engine.TimeScale`／`GetTree().Paused`。** 叠层只持状态（`Paused`／`RequestStep`），场景每帧问 `ShouldAdvance()` 决定推不推 —— 与顿帧 `Hitstop` 的「当帧不推进」同构。理由：可测、无引擎全局副作用（`TimeScale` 波及 InputRouter／动画，`Paused` 是全局还得给叠层自己设 `Always`）；`GP-14` 的 `TrainingRoom` 复用同一叠层的方法即可接线。
- **叠层的框从单一真相取，不各算一份。** 判定框读新加的 `Hitbox.ActiveBoxLocal`（命中查询用的同一份 `_shape`），受击框读新加的 `Hurtbox.BoxLocal`（碰撞形状用的同一份，`_Ready` 也改成用它建形状）。理由：叠层若自己按公式重算就可能与真实命中位置漂移，而「画面与判定对不上」正是这工具要帮人看见的病 —— 量具本身漂了就没意义。探针的 `hitbox-viz-matches-active` 是**独立**按 `SpecFor` 重算再比，两条路对上才算数。
- **挂世界空间 `Node2D`，不走 `UiRoot` 的 `CanvasLayer`。** dev 场景是纯 `Node2D` 世界、不建 `UiRoot`；框要画在世界坐标系里对上判定框真实位置。不派生 `Camera2D`、不引用 `UiLayer`，因此不被 `check_camera`／`check_worldui` 管到。

### 偏离

- **`SPEC` §2.2 把 `CombatDebugOverlay` 记为 `CanvasLayer`，实际做成世界空间 `Node2D`。** 那是早期节点类型猜测；`CanvasLayer` 是屏幕空间，画世界跟踪的框要多一次 world→screen 变换、更易与真实位置错开，而那一维恰是本工具要显示的。若 `GP-14` 想要屏幕空间的帧步进 HUD 文字，另加一层，不影响本叠层。
- **顿帧与 GdUnit4 的「实测选定」多由前序工作已定，本条据实记录而非重测。** 顿帧 `Hitstop` 在 `GP-11` 就落地（纯规则、无 `TimeScale`）；GdUnit4 在踩坑记录 30 已实测否决。本条把这两个既成决定收口到验收，并让帧步进复用顿帧的介入点。
- **三候选里两个 GDScript 插件（`animated-shape-2d`／`Fray`）未安装实测**，理由见验收结论：需求被 ~180 行 `Node2D` 覆盖、帧步进那半它们不做、引入 GDScript 依赖不划算。这是**有依据的不测**，不是漏测。
- **顺带改了三个既有文件取单一真相几何**：`Hitbox` 加 `ActiveBoxLocal`、`Hurtbox` 加 `HeightWorldPx`+`BoxLocal`（`_Ready` 改用之，几何等价）、`TrainingDummy` 暴露 `Hurtbox`。都不改行为 —— `hit_feedback`／`depth`／`player` 三个既有探针复跑无玩法回归佐证。

### 权衡

- **叠层画框只做数据级核对 + 一张截图，没逐像素核 1px 边框。** `CurrentHitboxWorld`／`CurrentHurtboxesWorld` ≙ 独立重算的几何（数据对），`screenshot` 证明渲染管线跑过，`_Draw` 只是把这份数据 `DrawRect`（trivial）。1px 非填充边框在逻辑→物理缩放下逐像素数不稳，为调试工具加脆弱的像素核对不划算。若将来叠层画错而数据对（`_Draw` 写错），这条覆盖不到 —— 记在此。
- **交互调试键 `V`／`P`／`.` 走 `_UnhandledKeyInput` 原始键码、登记进 `check_input_map` 的 `HARNESS_KEYS`，不进 `InputMap`。** 这几个是 dev 脚手架键，绑定表那套管不到，用登记制守它们不押在编辑器要用的键上。放**场景**（`CombatDebugDev`）不放**叠层**：叠层是可复用件（`GP-14` 会用），键是脚手架 affordance，分开让叠层对外只有方法。

### 待确认

- **作者实机确认**（唯一人工项）：用 `V` 看判定框/受击框、`P` 暂停、`.` 单步，能不能把 `US-001`~`US-004` 的手感调到位。命令 `python tools/run_local_check.py combat_debug_dev.py`（交互模式）。
- 「帧步进不改结算」已由单步命中木桩 + 硬直帧 ≙ 规则层证明，但**没做「整条挥击 stepped vs realtime 逐帧轨迹 A/B」**。若将来怀疑有细微差，补一条 A/B 判据即可 —— 当前三条（冻结、单步一帧、单步命中正确）已够。

## 验证结果（2026-09-12）

命令均从代码仓运行。改 `.cs` 后先 `dotnet build` 再跑图形探针。

| 入口 | 结果 | 判定 |
| --- | --- | --- |
| `verify.py`（完整 6 步） | 6/6，0 项必须修复；构建 0 错 0 警、测试 319/319、导出泄漏 0、跑产物 0 错；`texture_filter` 扫 75 份（含新增 3 个 .cs） | 通过 |
| `combat_debug_dev.py --probe` | **10/10**；日志守卫自证 25/25；判据 = 可视化 4（默认关、非 Active 不画判定框、Active 判定框 ≙ SpecFor、受击框 ≙ 角色几何）+ 帧步进 3（暂停冻结、单步恰一帧、单步命中结算正确）+ 截图 + 两条前提 | 通过 |
| `check_input_map.py` | 0 失败；`HARNESS_KEYS` 加 `V`/`P`/`Period` 与 `CombatDebugDev.cs` 逐个对上、无押编辑器键、`src/` 无直接轮询 | 通过（无回归） |
| `player_dev.py --probe` | 42/43（唯一失败 `focus-kept`，窗口失焦，环境前置项非玩法） | 通过（玩法判据全过，无回归） |
| `hit_feedback_dev.py --probe` | 72/73（唯一失败 `focus-kept`） | 通过（无回归；证明 `Hurtbox._Ready` 改用 `BoxLocal` 等价） |
| `depth_dev.py --probe` | 16/16 | 通过（无回归；`TrainingDummy` 改动等价） |

`focus-kept` 是带窗口探针在本机常见的环境失焦，非玩法缺陷（同 `GP-13`）；无窗口的 `verify.py` 6/6 为准。工作区根 `temp/` 未留残留，未提交、未推送。

机器通过不等于手感通过：这套工具**能不能把手感调到位**要作者实机用一遍，是上面「待确认」里唯一的人工项。
