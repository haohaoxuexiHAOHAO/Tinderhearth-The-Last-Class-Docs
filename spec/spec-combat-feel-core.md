---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-04
---

# SPEC：战斗手感核心（进攻侧竖切片 + 帧调优工具）

> 派生自：[`prd-combat-feel-core.md`](./prd-combat-feel-core.md)

## 1. 摘要

### 1.1 本 SPEC 覆盖什么

规格化 A1 的实现契约：一个独立的侧视训练房场景，主角由本地玩家驱动，对不还手的木桩做移动／跳／轻重连段／空中连击／闪避／冲刺，配打击反馈四件套（顿帧／闪白／击退／屏幕震动），外加 `ENG-6` 的最小帧调优工具（帧步进 + 判定框叠层）。战斗结算逻辑落规则层可单测，命中检测与表现落引擎层。**不接资源、不消费 `GP-2`。**

### 1.2 PRD 对应关系

- 来源：`prd-combat-feel-core.md`
- 用户故事：`US-001`~`US-006` 全覆盖
- 功能需求：`FR-1`~`FR-22` 全覆盖

### 1.3 设计决策一览

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 结算落点 | 帧步进状态机在 `rules/Combat`（纯 C#），引擎层只读结果 | 手感**逻辑**（连段帧、无敌窗口、击退量）能脱引擎单测；仿 `CameraRig` 模式 |
| 逐帧输入契约 | 新建 `CombatInput` 记录，不走 `ActorControl` 的粗粒度 `ActorIntent` | 帧精度的「按住／刚按／刚松 + 移动轴」`ActorIntent(单串)` 表达不了；`IActorController` 仍是「谁驱动」的登记表，A1 只实现玩家源（读 `InputRouter`），AI 源留 A2 |
| 手感可调量 | 放 `rules/Combat/CombatFeel.cs` 静态 `const`，量纲写名里 | 仿 `CameraFeel`；属 `GP-6` 的实测收敛落点，**不进 `GP-2`／`design/数值模型.md`／`game.json`** |
| 屏幕震动 | 复用 `GameCamera.Rig.Shake()` 与 `ShakeEnabled`，不新造 | `UI-5`／`UI-12` 已建好，`ShakeEnabled=false` 即恒零位移（`FR-15`） |
| 硬直与无敌 | 走一个最小统一状态载体（`rules/Combat/StatusEffects.cs`），带「可否解除」属性 | 正典「统一状态系统现在就成立」；A1 两种都不可解除，完整系统留后续 |
| 顿帧 | 全局 hitstop：命中时冻结战斗相关推进 N 帧，相机随之静止 | PRD §7；用 `Engine.TimeScale` 还是手动计时待评估（见 §10.2） |
| 场景 | 训练房是**独立新场景**，不动 `scenes/Main.tscn` | `Main.tscn` 的启动探针链是 `UI-1` 验收执行体，`verify.py` 跑产物与 `check_camera/hud` 都读它 |
| 命中检测 | 引擎层 `Area2D` 判定框／受击框，命中事件回喂规则层做结算 | 碰撞是引擎能力；结算（击退量／硬直帧／是否触发顿帧与震屏）是可测逻辑 |
| 主角美术 | `AnimatedSprite2D` + `SpriteFrames`，从 `ART-4` 登记的 samurai 表切 | 打击手感须真实动作帧才验得出；下载件占位、发行前替换（`ENG-12` 守） |

## 2. 场景与节点结构

### 2.1 在整体里的位置

训练房是一个可单独运行的开发场景，与 `Main.tscn` 平级、互不干扰。复用 `GameCamera(SideView)`（`UI-5`）与 `InputRouter`（`UI-7`）两个既有节点；**不接** `LevelHud`（无资源可显示）与世界空间 UI 的伤害数字（默认关）。

### 2.2 节点树

- **`TrainingRoom`**（`Node2D`）[新建场景]
  - `InputRouter`——本场景自己的输入门面实例
  - `GameCamera(SideView)`——`FollowTarget` 指向主角，`Router` 注入以备用
  - 地形（`StaticBody2D` + 占位几何）——地面与一两级平台，够验落地与空中连击
  - **`PlayerActor`**（`CharacterBody2D`）——主角：读 `InputRouter` → 建 `CombatInput` → 推进规则层状态机 → 驱动动画／判定框／位移
    - `AnimatedSprite2D`（samurai 占位）
    - `Hurtbox`（`Area2D`）
    - 攻击判定框（`Area2D`，仅 Active 帧启用）
  - **`TrainingDummy`**（`CharacterBody2D`，惰性）——木桩：受击进入硬直、闪白、按击退量位移，不还手、不死、无血条
    - `Sprite2D` 或 `AnimatedSprite2D`、`Hurtbox`
  - **`CombatDebugOverlay`**（`CanvasLayer`）——判定框／受击框可视化 + 帧步进控制，默认关，仅调试开

### 2.3 文件落点

**先行为后落点。** 规则层（纯 C#，`Tinderhearth.Rules.Combat`）：

- `rules/Combat/CombatFeel.cs` [新建]：全部可调帧数与量（前后摇、无敌窗口、顿帧时长、击退量、跳跃初速/重力、冲刺速度），`const`，量纲入名。
- `rules/Combat/CombatInput.cs` [新建]：一帧的输入快照（`readonly record struct`）。
- `rules/Combat/MotorState.cs` [新建]：移动／跳／落地／闪避／冲刺的运动学与状态，逐帧推进。
- `rules/Combat/ComboStateMachine.cs` [新建]：轻重连段与空中连击的段—相（Startup/Active/Recovery）状态机。
- `rules/Combat/StatusEffects.cs` [新建]：最小统一状态载体（硬直、无敌），带「可否解除」。
- `rules/Combat/HitResolution.cs` [新建]：由攻击轻重算击退量、硬直帧、是否重击（触发震屏）与顿帧帧数。

引擎层（`Tinderhearth.World`）：`src/World/PlayerActor.cs`、`TrainingDummy.cs`、`Hitbox.cs`／`Hurtbox.cs`、`Hitstop.cs`、`CombatDebugOverlay.cs` [均新建]；`scenes/TrainingRoom.tscn` [新建]；samurai 的 `SpriteFrames`（资源或运行时切分）[新建]。测试：`tests/Combat/*` [新建]。**不修改** `Main.cs`／`Main.tscn`。

## 3. 数据约定

### 3.1 类型定义

- `CombatInput(int MoveSign, bool JumpPressed, bool LightPressed, bool HeavyPressed, bool DodgePressed, bool SprintHeld)`——`MoveSign` ∈ {−1,0,+1}（侧视只用左右）；`*Pressed` 为「本帧刚按下」的边沿，`SprintHeld` 为持续态。
- `AttackPhase { Startup, Active, Recovery }`；`MotorPhase { Idle, Move, JumpRise, Fall, Dodge, Dash, Attacking }`。
- `HitReaction(int KnockbackWorldPx, int HitstunFrames, int HitstopFrames, bool IsHeavy)`——结算产物。
- `StatusKind { Hitstun, Invulnerable }`；状态载体条目 `(StatusKind Kind, int RemainingFrames, bool Removable)`，A1 两种 `Removable=false`。
- `CombatFeel` 全部为 `const int`（帧）或 `const int`（世界像素），无浮点魔法数散落。

### 3.2 关系

`PlayerActor`／`TrainingDummy` 各持一个 `MotorState` + 状态载体；`ComboStateMachine` 属 `PlayerActor`。命中时 `HitResolution.Resolve(weight)` → `HitReaction` → 施加到 `TrainingDummy` 的状态载体与位移、触发 `Hitstop` 与（重击时）`GameCamera.Rig.Shake()`。方向取值复用 `GP-9`：闪避方向 = `InputRouter.MoveDirection()` 当帧值，不缓冲。

### 3.3 存档与迁移

不涉及——训练房无存档。

## 4. 输入与状态机

### 4.1 输入映射

全部复用 `InputActions` 既有动作，无新增绑定：`move_left/right`、`jump`、`attack_light`、`attack_heavy`、`dodge`、`sprint`。经 `InputRouter.IsJustPressed/IsPressed/MoveDirection` 读取（`check_input_map` 守直接轮询）。`guard` 与 6 技能位本切片不读。

### 4.2 状态与迁移（主角）

| 当前 | 事件 | 迁移到 | 守卫／副作用 |
| --- | --- | --- | --- |
| Idle/Move | `MoveSign≠0` | Move / Idle | 地面移动速度由 `CombatFeel` |
| Idle/Move | `JumpPressed` 且在地面 | JumpRise | 跳跃初速 |
| JumpRise | 到达顶点或计时 | Fall | 重力 |
| Fall | 落地 | Idle | 打断空中连段 |
| Idle/Move | `Light/HeavyPressed` | Attacking(段1) | 进入 Startup |
| Attacking(段N,Recovery) | `Light/HeavyPressed` 在衔接窗口内 | Attacking(段N+1) | 仅连段续接，**无取消**（`GP-4`） |
| Attacking(Recovery) | 窗口过／无输入 | Idle | 回落 |
| JumpRise/Fall | `Light/HeavyPressed` | Attacking(空中段) | 落地即打断 |
| Idle/Move | `DodgePressed` | Dodge | 起 `Invulnerable` 窗口；方向取按下瞬间（`GP-9`） |
| Move | `SprintHeld` 且 `MoveSign≠0` | Dash | 无无敌；松开或停移即回 Move |

**A1 不做取消／派生**：攻击段只能续接下一连段，不能取消到闪避／防御（防御本就不在 A1）。闪避与冲刺只从非攻击态进入。

### 4.3 边界情况

- 木桩已在硬直中再受击：刷新硬直帧（取新值，不叠加）。
- 同一次挥击的判定框对同一受击框只结算一次（每次挥击一个已命中集合）。
- 顿帧期间不接受新输入推进（双方与相机一同静止），顿帧结束继续。
- 无方向输入时闪避：`MoveSign=0` → 取「面朝方向」翻滚（保持当前朝向）。
- samurai 缺某动作帧：退回占位几何或明显标记，不崩（见 §6）。

## 5. 核心逻辑

每物理帧（`_PhysicsProcess`），若不在 hitstop：

```
input = BuildCombatInput(router)              // 读 InputRouter，组装边沿与持续态
motor.Tick(input); combo.Tick(input)          // 推进帧计数与状态迁移
applyVelocity(motor.State)                     // 由状态给速度：移动/跳/闪避冲刺/重力
sprite.Play(animFor(motor, combo))             // 状态→动画
hitbox.SetEnabled(combo.Phase == Active)       // 仅 Active 帧开判定框
for dummy in overlappingHurtboxes(hitbox):
    if dummy not in combo.CurrentSwingHitSet:
        r = HitResolution.Resolve(combo.CurrentWeight)
        dummy.status.Apply(Hitstun, r.HitstunFrames)
        dummy.Knockback(r.KnockbackWorldPx * facing)
        dummy.Flash()
        Hitstop.Begin(r.HitstopFrames)          // 顿帧：冻结推进
        if r.IsHeavy: camera.Rig.Shake()        // 屏幕震动（ShakeEnabled 为总开关）
        combo.CurrentSwingHitSet.Add(dummy)
```

`motor` 与 `combo` 的迁移逻辑（§4.2）全在规则层、按帧推进，可用单测断言「第 X 帧进入 Active」「无敌窗口起止帧」「连段窗口内/外的续接与回落」。引擎层只做 `BuildCombatInput`、`applyVelocity`、动画、`Area2D` 重叠查询与表现。

## 6. 失败处理

| 失败模式 | 触发 | 表现 | 恢复 |
| --- | --- | --- | --- |
| samurai 动作帧缺失 | 某动作无对应帧 | 该动作退回占位几何 + 日志明确列出缺哪个 | 补生成占位或作者补帧；不阻塞其余动作 |
| `InputRouter` 未注入 | 场景组装漏接 | 启动即报错（不静默不动） | 场景自检断言门面在位 |
| 判定框在 Active 外误开 | 逻辑错 | 帧步进叠层里可见判定框在错误帧亮 | 单测钉 Active 帧区间 |
| 顿帧未归还 | hitstop 计时漏清 | 画面卡死 | hitstop 帧数为有限常量、每帧递减到 0 自动解除，单测覆盖 |
| 屏幕震动引起不适 | 玩家敏感 | —— | `ShakeEnabled=false` 恒零位移（既有能力） |

### 说明

A1 无「资源不足」「数据缺失」路径（不读数值、不读存档）；mod／外部调用不涉及。

## 7. 表现与性能

同屏只有 1 主角 + 1 木桩，负载可忽略；`Area2D` 判定极少。顿帧按帧冻结，不产生累积开销。**同屏 10–15 敌的性能与感知系统开销是 A2 的事**，本切片不涉及。判定框叠层仅调试开，不进发行包表现（`ENG-12` 守下载件与非自绘件不进包，叠层是代码非素材）。

## 8. 测试映射

### 8.1 自动化覆盖

规则层单测（`tests/Combat`，xunit `[Fact]`/`[InlineData]`，禁 `[MemberData]`）：连段状态机的段—相迁移与衔接窗口、空中连段落地打断、闪避无敌窗口起止帧、闪避方向取当帧值、`HitResolution` 的击退量／硬直帧随轻重变化、硬直刷新不叠加、hitstop 帧数有限且自解除、状态载体的「可否解除」标志。屏幕震动关闭恒零位移复用 `CameraRig` 既有测试。

### 8.2 验收标准对应表

| US／FR | 测试 | 类型 | 说明 |
| --- | --- | --- | --- |
| `US-001`/`FR-4` | 运动学纯函数 | 单元 | 移动/跳/重力；手感「跟手」实机 |
| `US-002`/`FR-5~7` | 连段状态机迁移 | 单元 | 段—相、衔接窗口、空中落地打断 |
| `US-003`/`FR-8~10` | 无敌窗口、闪避方向、冲刺显式 | 单元 | 方向取当帧（`GP-9`） |
| `US-004`/`FR-11~16` | `HitResolution`、硬直载体、震屏关零位移 | 单元 | 「打得实」实机 |
| `US-005`/`FR-19,22` | 帧步进不改结算、参数快照导出 | 单元＋人工 | `ENG-6` 评估结论人工核 |
| `FR-20` | 规则层不引 Godot | 编译＋`verify.py` | 结构保证 |
| `FR-21` | 无伤害数字/无血条 | 人工核 | 训练房观察 |
| `US-006` | 端到端主/失败路径 | 集成 | `verify.py` 全绿 |

### 8.3 只能实机确认的项

顿帧的「实」、前后摇与连段衔接的节奏、闪避无敌感、冲刺显式感、四件套合起来是否「打得实」且顿帧不断输入节奏、1080p/1440p 下字与像素清晰。实机步骤见 PRD `US-006` 清单。存证：帧步进截图 + 参数快照落 `logs/`。

## 9. 实现顺序

### 9.1 分批

规则层先行（可脱引擎单测）：`CombatFeel` + `MotorState` + `ComboStateMachine` + `StatusEffects` + `HitResolution`。再引擎层：`PlayerActor` 移动/跳/连段 + 动画 → 命中检测 + 四件套 + 木桩 → 训练房场景组装。并行：`ENG-6` 工具评估与最小自建。最后端到端 + 实机。

### 9.2 issue 映射

编号由 `/to-issues` 分配（玩法用 `GP`、工具用既有 `ENG-6`）；下表是拆分建议。

| 建议条目 | 覆盖 SPEC 章节 | 优先级 | 依赖 |
| --- | --- | --- | --- |
| 规则层：运动与连段状态机 + 手感常量 + 单测 | §3、§4.2、§5、`CombatFeel` | 中 | 无 |
| 规则层：统一状态载体 + 命中结算 + 单测 | `StatusEffects`、`HitResolution` | 中 | 上条 |
| 引擎层：主角运动/跳/连段 + samurai 动画 | `PlayerActor`、`SpriteFrames` | 中 | 规则层两条 |
| 引擎层：命中检测 + 四件套 + 木桩 | `Hitbox`、`Hitstop`、`TrainingDummy` | 中 | 上条 |
| `ENG-6`：帧调优工具评估 + 最小自建 | `CombatDebugOverlay`、§10.2 | 中 | 引擎层可跑后 |
| 训练房场景 + 端到端 + 实机确认 | `TrainingRoom.tscn`、§8 | 中 | 全部 |

## 10. 待确认问题与风险

### 10.1 待确认问题

无。立项六问已在 PRD 答复并 `approved`。

### 10.2 技术风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 顿帧用 `Engine.TimeScale=0` 可能波及 `InputRouter`、动画树等全局 | 冻结范围过大或输入丢失 | 评估手动 hitstop（只冻结战斗推进与相机）对比 `TimeScale`，实测选定并记 `ENG-6` |
| `Fray`/`animated-shape-2d` 在 4.7.2+`net10.0` 未验、`Fray` 是 GDScript 需互操作 | 工具选型落空 | `ENG-6` 先实测三候选再决定自建补哪层，不预设采用 |
| samurai 动作帧覆盖不足 | 手感验不全 | 实现首步先核帧覆盖度，缺则补生成占位或标注（PRD 已列） |
| 引擎内帧级测试框架未选 | 帧级行为只能人工 | 帧级/场景测试框架属 `ENG-6` 评估；规则层逻辑走既有 xunit，不阻塞 |

### 10.3 假设

- 本 SPEC 基于**实际阅读**代码仓的真实签名（`InputRouter`、`CameraRig`/`GameCamera`、`ActorControl`、`CameraFeel`、`Main.cs`），非空仓推断。
- **未验证**：`GameCamera.Rig.Shake()` 在训练房场景（非脚手架）下的表现同 `UI-5` 脚手架——验证办法：训练房里触发重击看位移与关开关。
- **未验证**：samurai 表能切出全部所需动作帧——验证办法：核 `assets/downloaded/samurai/` 与 `asset-registry.json` 登记。
- **未验证**：顿帧对 `InputRouter` 事件流的影响——验证办法：hitstop 期间按键，看解除后是否丢输入。
