---
type: workdoc
status: archived
owner: project
last_verified: 2026-09-01
---

> **只读归档。** 此文件是 `UI-1` 于 2026-09-01 归档时的历史记录。现行事实见台账[已归档编号](../../../spec/issues/README.md)对应行与代码仓实现文件。**不得修改此文件的正文内容。**

# UI-9：世界空间 UI（读条、精英血条、伤害数字）

## 目标

读条、血条与伤害数字画在角色所在的世界位置并跟着角色走，使玩家能同时看见"我在读条"和"谁在靠近"。

## 来源

- PRD：[`spec/prd-ui-framework.md`](prd.md) 的 `US-007`（世界空间那一半；屏幕空间部分在 `UI-8`）
- [战斗与关卡 · 读条](../../../canon/gameplay/战斗与关卡.md)明确否掉"画在界面角落"这一放法；同页定血条只给精英与 BOSS、伤害数字默认关闭

## 依赖

`UI-6`（层级里"世界空间 UI"这一层）。与 `UI-8` 可并行。

## 验收标准

- [x] 读条为一圈填充的圆形进度条，画在执行者身上，随角色移动 —— 圆环用 `DrawArc` 画进度弧（从 12 点顺时针，`WorldUiLayout.ArcRadius/ArcWidthPx/ArcSegments`），底环用占位件 `cast-ring.png`；挂 `UiLayer.WorldSpace`、每帧 `Position = 执行者.GlobalPosition`。探针 `[世界UI]` 的「挂载层」「跟随」两条判据 ＋ 规则层 `CastState` 单测。弧形观感在动态与 2 倍缩放下随第 5／6 条作者实机一并看
- [x] 受击中断读条（中断不消耗物品这条属玩法实现，本条只保证表现能中断）—— `CastState.Visible = Active && !Interrupted`，中断即隐藏；探针「中断」判据 ＋ 单测
- [x] 血条只对精英与 BOSS 出现，杂兵没有血条 —— `EliteHealth.ShowsBar = Elite|Boss`；探针「血条精英」判据（精英可见、杂兵不可见）＋ 单测
- [x] 伤害数字默认关闭，设置里可开启 —— `WorldUiOptions.ShowDamageNumbers` 默认 `false`（呈现开关，照 `CameraFeel` 先例不进 `game.json`）；探针「伤害数字」判据（关时不冒、开后才冒）＋ 单测
- [x] 世界空间 UI 随相机缩放正确定位：侧视 2 倍缩放下不偏移、不变形 —— 机制已机器验证：世界空间层 `FollowViewportEnabled = true`（探针「缩放跟随」判据），子节点用世界坐标自动跟相机变换与缩放。**作者 2026-09-01 实机确认不偏移、不变形**
- [x] 这些元素在 12px 字号下仍可读（数字与短标签）—— 字体机制已验：世界文字用 `ThemeDB.FallbackFont`、字号 `UiMetrics.FontSize = 12`（探针「字体」判据），与 `UI-8` 作者已确认可读的同一份像素字体。**作者 2026-09-01 实机确认可读**
- [x] 作者实机确认：脚手架 `C` 读条三态、`B` 精英血条、`M` 伤害数字开关、`N` 冒伤害，看 12px 元素在侧视 2 倍缩放下可读、随角色走不偏移不变形（**2026-09-01 确认**）

## 实现笔记

> 由 `/note-it` 填写。

### 设计决策

- **三个元素都挂 `UiLayer.WorldSpace`（不是 `Hud`）。** 这是本条核心约束：正典否掉「读条画在界面角落」、要求画在执行者身上。世界空间层开了 `FollowViewportEnabled`，子节点用世界坐标、自动跟相机变换与 2 倍缩放 —— 元素只要每帧 `Position = 目标.GlobalPosition` 就对齐，不必手算世界到屏幕投影。`UI-9` 是这层的首个消费者。守卫 `check_worldui.py` 静态核盯住挂载点不被改成 `Hud`。
- **规则／引擎分层照 `UI-8`。** 几何与数据在 `rules/Ui`：`WorldUiLayout`（圆环半径／弧宽／弧段数、血条宽高／偏移、伤害数字起点／飘距／存活时长，全用 `UiMetrics.*` 换算、无字面量）、`WorldUiViewModel`（`EnemyRank`、`CastState`、`EliteHealth`、`WorldUiOptions`，坏值抛、比率钳）。引擎层 `WorldSpaceUi` 只画、值取自视图模型，不写玩法数字（读条时长、血量上限归 `GP-2`）。
- **引擎层用 `Node2D` ＋ `_Draw`。** 读条圆环 `DrawArc`（进度弧）、精英血条 `DrawRect`（底槽 `Track` ＋ 填充 `Health`）、伤害数字 `DrawString`（`Hot` 色、12px）。`cast-ring.png` 作底环 `Sprite2D` 子节点，进度弧代码画在环上。给 `WorldUiLayout.ArcSegments`（=24）一个常量，避免 `DrawArc` 的点数写成字面量。
- **冷暖色全用不透明色，伤害数字到期直接消失、不做半透明淡出**（像素绘制原则 §9）。色取自 `PixelTheme.ToColor(HudPalette.*)`，与 HUD 同源。
- **伤害数字开关是规则层 flag**（`WorldUiOptions.ShowDamageNumbers` 默认 `false`），照 `CameraFeel` 先例不进 `game.json` —— 它是呈现偏好，不是玩法配置。
- **`WorldSpaceProbe` 排在启动探针链最前、任何相机之前。** 那时世界空间层画布变换是恒等，「圆环位置 = 目标世界坐标」测起来干净；且全是逻辑与节点关系检查、不截图，headless 下照样跑（与 `HudProbe`／`CameraProbe` 不同，那两个要真窗口）。跑完收掉自己挂在层上的元素、让层回到干净，再 `Finished` 串起相机自检。
- **守卫 `check_worldui.py` 两核**：静态核（挂载层 = `WorldSpace`、代码不碰别的层）＋ 行为核（读 `[世界UI]` 判据零 FAIL、自报条数一致、判据标签集合与登记逐条对上）。自证 `selfcheck_worldui.py` 用 10 条真实缺陷形状撞过。
- **脚手架调试键 `C`／`B`／`M`／`N`**（读条三态／精英血条／伤害数字开关／冒伤害），避开编辑器要用的 `F8`，进 `check_input_map.py` 的 `HARNESS_KEYS` 登记制。

### 偏离

- 无。按方案实现：规则层几何／数据 ＋ 引擎层世界空间节点 ＋ 探针 ＋ 守卫 ＋ 自证。

### 权衡

- **纹理过滤覆盖不在 `check_worldui.py` 里查。** 那条是全仓规则、已归 `ENG-13`（`check_assets.py` 扫 `src/` ＋ `rules/` 的 `.cs`，本条两个引擎文件也在其内）。再抄一份就是第二份真相。本条的不变式是挂载层 ＋ 行为，不是无字面量，所以刻意不做 `check_hud` 式的无数字扫描。
- **行为核用 `--headless`。** 探针排最前、恒等变换下测，快且不需窗口；代价是「2 倍缩放下的视觉」测不了（要截图），那条留作者实机（第 5／6／7 条）。这是有意的分工 —— 机制（`FollowViewport`、12px 像素字体）机器验，视觉作者验。
- **演示数值是脚手架取值。** `CastDemoSeconds = 2.0`、`DemoDamageAmount = 12`、演示血量 `demoMax = 20` —— 同 `WalkPixelsPerSecond` 先例，不是玩法数值（归 `GP-2`／战斗实现）。脚手架能演示、而引擎不写死平衡。

### 待确认

1. **侧视 2 倍缩放下不偏移、不变形**（第 5 条验收）：作者实机看读条圆环／精英血条／伤害数字。调试键 `C`（读条三态）、`B`（精英血条，配 `F5` 收拢剪影看一排）、`M`（伤害数字开关）、`N`（冒伤害），或 `harness_shot.py` 存图。
2. **12px 可读**（第 6 条验收）：世界元素在 2 倍缩放下渲染更大（约 24 物理像素），预期比 HUD 的 12px 中文更清；请实机确认伤害数字与短标签读得清。
3. **读条圆环在侧视 96px 侍武士上的相对大小**：16px 直径配俯视 32px 角色合适，侧视大精灵上可能偏小。几何是规则层已定并单测的值；若作者觉得小，作为后续微调、不阻塞本条。
4. **`check_input_map.py` 行为核 2 FAIL（环境问题，非本条回归）**：「摇杆小幅漂移不抢走提示 → 实际 Gamepad」＋ 自检 16／17。据实定位：`AxisSwitchThreshold = InputBindings.TriggerDeadzone = 0.5`，探针只注入 0.3（< 0.5 本不该切），日志却出现「设备切换 → Gamepad」→ 只可能是外部 ≥ 0.5 事件 = 物理手柄连着且摇杆／扳机漂移过阈值，在探针时窗注入了真事件。输入代码未改、`UI-7` 收尾时该测通过，故非 `UI-9` 回归；`verify.py` 的 smoke 只查 `[启动]` 标记与 `ERROR` 行、不解析 `[输入]` 判据，不受影响。请作者**断开手柄（或勿碰摇杆）后重跑 `python tools/check_input_map.py`**，确认回到 17／17。本条只新增 `C/B/M/N` 键登记，脚手架调试键静态核已过。

## 验证结果

> 由 `/verify-round` 填写。只写实际运行过的内容。

| 命令 | 结果 | 判定 |
| --- | --- | --- |
| `python tools/verify.py`（完整门禁） | 5／5 步过：素材（28 `.png` ＋字体，`texture_filter` 扫 46 份 0 覆盖）、构建 0 错 0 警、测试 168／168（143 ＋新增 25）、导出泄漏 0（包内 88 条）、跑产物 `[启动]` 10 行 0 错误；20.6s，`EXIT=0` | 通过 |
| `python tools/check_worldui.py` | 静态核：挂载层 = `WorldSpace`、代码不碰别的层；行为核（headless 真机启动）：`[世界UI]` 7／7 判据全 PASS、自报条数一致、标签集合与登记逐条对上；`EXIT=0` | 通过 |
| `python tools/selfcheck_worldui.py` | 10 条真实缺陷形状（5 解析变异 ＋ 2 直接 ＋ 2 静态注入）全部按预期拦下、还原后复验干净；`EXIT=0` | 通过 |
| `python tools/check_input_map.py` | 脚手架调试键静态核过：16 键含新增 `C/B/M/N` 逐个对上、无一押编辑器 `F8`。行为核 2 FAIL（摇杆小幅漂移 → 实际 Gamepad、自检 16／17）—— 据实定位为物理手柄漂移过 0.5 阈值注入真事件，环境问题、非本条回归（输入代码未改），待作者断开手柄重跑 | 脚手架键通过；2 FAIL 属环境，待作者复核（见「待确认」4） |
