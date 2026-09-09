---
type: workdoc
status: draft
owner: project
last_verified: 2026-09-09
---

# SPEC：战斗手感核心（进攻侧竖切片 + 帧调优工具）

> 派生自：[`prd-combat-feel-core.md`](./prd-combat-feel-core.md)

## 1. 摘要

### 1.1 本 SPEC 覆盖什么

规格化 A1 的实现契约：一个独立的侧视训练房场景，主角由本地玩家驱动，对不还手的木桩做移动／跳／轻重连段／空中连击／闪避／冲刺，配打击反馈四件套（顿帧／闪白／击退／屏幕震动），外加 `ENG-6` 的最小帧调优工具（帧步进 + 判定框叠层）。战斗结算逻辑落规则层可单测，命中检测与表现落引擎层。**不接资源、不消费 `GP-2`。**

### 1.2 PRD 对应关系

- 来源：`prd-combat-feel-core.md`
- 用户故事：`US-001`~`US-006` 全覆盖
- 功能需求：`FR-1`~`FR-22` 全覆盖；2026-09-09 的纵深轴范围变更加了 `FR-23`~`FR-28`，其中 `FR-23`／`FR-24` 与 `FR-28` 的纵深速度部分由 `GP-15` 落地（本 SPEC §3.1、§4.3、§5），`FR-25`（纵深容差命中）归 `GP-16`、`FR-26`／`FR-27`（纵深排序与代码影子）归 `ENG-15`、`FR-28` 的容差部分随 `GP-16`

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
| 主角美术 | `AnimatedSprite2D` + `SpriteFrames`；**已改为作者自绘逐帧件**（`ART-6`），samurai 仅留给相机脚手架 | 打击手感须真实动作帧才验得出；自绘测试木偶仍登记为不得进包、发行前替换（`ENG-12` 守） |
| 受击闪白 | **归代码，动画只提供受击姿态**（`ART-6`，2026-09-08 定） | 代码侧能按轻重分调时长、跟顿帧一同冻结、做成可关的无障碍项，且每个新敌人不必各画一套；进仓精灵表因此不许出现整帧单色的帧 |
| 判定框 | **按轻重分开**，取值由 Active 帧的实测伸展导出（轻 18×4、重 22×16，中心距脚底 18） | 画面上轻拳伸 18px、重拳 22px，共用 28×28 会让「重击打得更远」读成「重击不实」，而这不报错；仍是 `GP-6` 的未校准初值 |
| 帧框与判定框的真相 | 引擎常量与素材登记表**由守卫绑定**，不各写一份 | 引擎读不到登记表（`tools/` 带 `.gdignore`、不进包）；三个漂移方向（改素材／改 Active 窗口／改常量）都被 `check_assets.py` 拦下 |
| 运动模型（`GP-15`，2026-09-09 改） | 横向／纵深／跳跃高度**三轴分离**；纵深连续、钳在 48px 带内、离地期间锁定 | 正典把战斗关卡定为带连续可行走纵深的横版；分道会把「往里挪半步躲开」变成「换道」，那是两种手感 |
| 纵深位置的所有权（`GP-15`） | 速度与**位置**都在 `MotorState.DepthWorldPx`，引擎层只读、不再积分（那会得到两倍位移且不报错） | Godot 2D 的两个轴已被占满，且 48px 钳制要能脱引擎单测。代价与执行体见代码仓 `ARCHITECTURE.md` 与 [`issue-GP-15`](./issues/issue-GP-15-depth-axis-motion.md) |
| 纵深的两个落点（`GP-15`） | 带宽进 `rules/Combat/DepthBand.cs`（正典几何账，`ENG-16` 可能回改）；纵深行走与**纵深闪避**两个速度进 `CombatFeel`，都是未校准初值 | 48px 不是只能实机调的手感量，混进 `CombatFeel` 会让人以为它可以凭手感改；纵深闪避另设速度是因为横向那个 168 放到 48px 带上会让每次闪避都撞带沿，**落点由钳制而不是输入决定**。详见 `issue-GP-15` |
| 绘制排序（`ENG-15`） | 两个键（纵深为主、同纵深时脚底为次）算在 `rules/Combat/DepthRendering.cs`，引擎层只写 `z_index`；**不用** `y_sort_enabled`（它只排一个键，屏幕 Y 里混着跳跃高度） | 理由与代价见 [`issue-ENG-15`](./issues/issue-ENG-15-depth-sorting-shadow.md)，不在此复制第二份 |
| 纵深的绘制偏移与影子（`ENG-15`） | 碰撞地面对应**带中线**（偏移 ＝ 纵深 − 24，地形按 48px 带画）；影子是代码画的不透明扁椭圆，位置取地面投影点（射线每帧问）、随高度**只缩小不变淡** | 同上。不变淡是[像素绘制原则 §9]「只用完全透明或完全不透明」的直接推论 |

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
- `rules/Combat/DepthBand.cs` [新建，`GP-15`]：可行走纵深带（宽度、前后沿、中线、排间距、钳制），正典几何账的唯一落点。
- `rules/Combat/DepthRendering.cs` [新建，`ENG-15`]：纵深绘制的规则 —— 排序两键（`DepthSubject`／`Compare`／`DrawOrder`）、绘制偏移、影子随高度的缩放。
- `rules/Combat/MotorState.cs` [新建]：移动／跳／落地／闪避／冲刺的运动学与状态，逐帧推进；`GP-15` 起含纵深轴与它的位置。
- `rules/Combat/ComboStateMachine.cs` [新建]：轻重连段与空中连击的段—相（Startup/Active/Recovery）状态机。
- `rules/Combat/StatusEffects.cs` [新建]：最小统一状态载体（硬直、无敌），带「可否解除」。
- `rules/Combat/HitResolution.cs` [新建]：由攻击轻重算击退量、硬直帧、是否重击（触发震屏）与顿帧帧数。

引擎层（`Tinderhearth.World`）：`src/World/PlayerActor.cs`、`TrainingDummy.cs`、`Hitbox.cs`／`Hurtbox.cs`、`Hitstop.cs`、`CombatDebugOverlay.cs` [均新建]；`scenes/TrainingRoom.tscn` [新建]；samurai 的 `SpriteFrames`（资源或运行时切分）[新建]。测试：`tests/Combat/*` [新建]。**不修改** `Main.cs`／`Main.tscn`。`ENG-15` 追加 `src/World/DepthVisual.cs`（`IDepthActor` ＋ 纵深可视根：偏移、影子、地面射线）与 `src/World/DepthSortedLayer.cs`（收集子节点、写 `z_index`、自报覆盖量）；角色的可视子节点一律挂在可视根下，**纵深偏移因此只有一处来源**；探针入口 `scenes/DepthDev.tscn` ＋ `tools/depth_dev.py`。

## 3. 数据约定

### 3.1 类型定义

- `CombatInput(int HorizontalSign, int DepthSign, bool JumpPressed, bool LightPressed, bool HeavyPressed, bool DodgePressed, bool SprintHeld)`——两个方向轴各规整到 {−1,0,+1}（`HorizontalDirection`／`DepthDirection`），`DepthSign` 正为向前（靠近镜头）；`HasDirection` 表示这一帧有没有任何方向输入；`*Pressed` 为「本帧刚按下」的边沿，`SprintHeld` 为持续态。**原字段名 `MoveSign` 已改为 `HorizontalSign`**（`GP-15`）：加了纵深之后「移动轴」有两个，旧名字会让「把纵深接到横向字段上」成为看不出来的错。
- `DepthBand`（静态）——`WidthWorldPx=48`、`BackWorldPx=0`（最靠后）、`FrontWorldPx=48`、`CenterWorldPx=24`、`RowSpacingWorldPx=16`，加 `Clamp`／`Contains`。**0 在最靠后、与屏幕向下同向**是有意选的：纵深值与「绘制时往下偏移多少世界像素」是同一个数、同一方向，不用取反，而符号写反**不报错**，只会让画面前后关系与命中判定相反。`MotorState` 的纵深三项——`DepthWorldPx`（位置，恒在带内，连续量不是轨道号）、`DepthVelocity`（**本帧真实发生**的速度，钳在带沿时为 0 而不是「按着键所以在动」的目标值）、`IsDepthAirLocked`（**只表示离地锁定**；出招定身时纵深速度也是零，但那是与横向同一条封锁口径）。摆位走 `PlaceDepth`（直接改位置、不产生速度）。
- `AttackPhase { Startup, Active, Recovery }`；实际 `MotorPhase { Grounded, Airborne, Dodge, Dash }`，待机/移动由横速区分，上升/下落由竖速区分，攻击由独立连段机表达。
- `HitReaction(int KnockbackWorldPx, int HitstunFrames, int HitstopFrames, bool IsHeavy)`——结算产物。
- `StatusKind { Hitstun, Invulnerable }`；状态载体条目 `(StatusKind Kind, int RemainingFrames, bool Removable)`，A1 两种 `Removable=false`。
- `CombatFeel` 常量按成员名区分帧、世界像素、世界像素/秒和世界像素/秒²，固定60Hz换算；手感量是未校准初值。

### 3.2 关系

`PlayerActor` 持 `ActorCombatState`（含 Motor 与连段）；`TrainingDummy` 只持独立统一状态载体，不建无用的 Motor。命中时 `HitResolution.Resolve(weight)` → `HitReaction` → 施加到 `TrainingDummy` 的状态载体与位移、触发 `Hitstop` 与（重击时）`GameCamera.Rig.Shake()`。方向取值复用 `GP-9`：闪避方向 = `InputRouter.MoveDirection()` 当帧值，不缓冲。

### 3.3 帧推进所有权（GP-11）

- `MotorState.Statuses` 是该角色唯一载体；`MotorState.Tick` 在每个非顿帧逻辑帧开头推进所有状态一次，调用方不得另行推进它。无运动机的独立载体由角色逻辑拥有者按相同顺序推进。
- `Apply(kind, N)` 立即生效，之后第 N 次 `Tick` 到期；帧开头先递减旧状态，再施加本帧的新状态。闪避第 2 帧注册 11 帧无敌，保持原有 `[2,13)` 窗口；同种刷新用新时长覆盖，零／负时长和未知种类拒绝且不改变原状态。`TryRemove` 对 A1 两种状态均返回 false。
- `HitResolution.Resolve(ComboKind)` 只接受 Light／Heavy，拒绝 None 与未知值。击退产物为正世界像素距离，由引擎层施加方向；不是速度。
- 纯规则层 `HitstopTimer` 在命中帧末 `Begin(N)`，外层随后每个物理帧先调 `Tick()`；返回 true 就跳过本帧战斗与相机推进（包括最后一个冻结帧），下一帧恢复。这个时钟本身不能冻结。再次 Begin 替换剩余帧，非正时长拒绝。引擎冻结实现仍属 GP-13。
- 上述顺序由 `tests/Combat/StatusEffectsTests.cs`、`HitResolutionTests.cs`、`MotorStateTests.cs` 守住；未来引擎是否按此调用须在 GP-13 接入时验证，本轮未验证引擎冻结或实机手感。

### 3.4 存档与迁移

不涉及——训练房无存档。

## 4. 输入与状态机

### 4.1 输入映射

全部复用 `InputActions` 既有动作，无新增绑定：`move_left/right`、**`move_up/down`**（`GP-15` 起驱动纵深，`UI-7` 早已绑好 W/S 与左摇杆 Y）、`jump`、`attack_light`、`attack_heavy`、`dodge`、`sprint`。经 `InputRouter.IsJustPressed/IsPressed/MoveDirection` 读取（`check_input_map` 守直接轮询）；纵深取 `MoveDirection().Y` 且**不取反** —— `move_down` 为正，`DepthBand` 的正方向也是向前。`guard` 与 6 技能位本切片不读。

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
- 闪避方向（`GP-15` 起是二维，`GP-9` 的「取按下瞬间」口径不变）：**两个轴都没按**才取「面朝方向」翻滚；只按纵深时是纯纵深翻滚（横向速度为 0、**朝向不变** —— 侧视精灵只有左右两面，纵深输入不改朝向）；两个方向在起手那一瞬一起锁定，翻滚途中改方向无效。
- 离地期间纵深锁定、落地即自动解锁，**闪避途中掉出平台也照锁**（翻滚不是纵深的豁免，否则「空中不改纵深」有一个用闪避就能绕开的口子），横向翻滚位移照给满；冲刺只加横向，按住冲刺 + 只按纵深不进 `Dash` 相位、纵深仍走行走速度。
- samurai 缺某动作帧：退回占位几何或明显标记，不崩（见 §6）。

## 5. 核心逻辑

每物理帧（`_PhysicsProcess`），若不在 hitstop：

GP-12 实现校正：`ActorCombatState.Tick(input, onFloor)` 为唯一仲裁入口，先连段后运动；已有闪避拒绝攻击（含退出帧），已有攻击在结束帧仍不允许跳闪取消，空闲同帧攻击优先于跳闪。`MoveAndSlide` 后 `AfterMove` 立即处理撞顶与空中连段落地，不再 Tick。`ICombatController` 扩展控制器帧能力，角色每帧从登记表取源；无战斗能力控制器为空输入。动画手动按物理帧选择纹理，不调用自动播放。

GP-12 运动帧契约：规则持速度（世界像素/秒），引擎持位置并由 MoveAndSlide 按60Hz积分，不重复乘步长。普通横速按 CombatFeel 加/减速度逐Tick逼近并夹紧目标；反向或减小目标幅值使用减速率，地面攻击立即定身，空中也走同一曲线。1040/1560世界像素/秒²是未校准初值，对104px/s对应6帧起步/4帧停止。闪避起手算第0帧，18次Tick均给横速；第17帧退出相位但保留本次输出，下一Tick才读普通输入，未碰撞位移为168×18/60=50.4世界像素。离平台不清竖速，沿用重力累计；AfterMove在撞顶/落地时清被阻挡竖速、墙碰撞时回传引擎横速，不推进任何时钟。图形探针覆盖真实撞顶及下一帧、轻3重2每段三相、完整闪避位移和离台落地；规则测试覆盖水平曲线及碰撞计时。

GP-15 运动帧契约（三轴，2026-09-09 修订上面那条）：横向与跳跃高度照旧「规则持速度、引擎持位置」；**纵深的速度与位置都在规则层**，`AdvanceDepth` 在每个 Tick 恰好调一次（普通路径与闪避路径各自调它），按固定 60Hz 步长积分后钳进 `DepthBand`，钳住时报真实发生的速度而不是目标值。离地锁纵深、落地解锁，出招在地面时横向与纵深一同归零，冲刺只改横向。纵深不做加速曲线（整条带只有 48px，横向那条 6 帧起步的曲线会在到速前吃掉六分之一条带），两轴同按也不做对角归一（归一会让两轴互相牵制，与三轴分离相反；代价是斜走合速度快约 15%，未实机验）。规则层单测覆盖钳制、连续性（停在非排位值上）、空中锁与落地解锁、三轴不串、出招定身、闪避二维方向锁定与途中掉台锁纵深；引擎侧另有 4 条图形判据钉「门面移动向量 Y → 纵深」这段接线，详见 [GP-15](./issues/issue-GP-15-depth-axis-motion.md)。

GP-13 已实现独立 `HitFeedbackDev.tscn`，完整训练房与调优工具仍属 GP-14/ENG-6。实际帧序为：外层 Hitstop.Tick → 若冻结则返回 → PlayerActor.AdvanceCombat（含碰撞后取消）→ TrainingDummy.AdvanceCombat → GameCamera.Advance → Hitbox.Resolve → 新命中 Begin。命中帧不消耗顿帧；输入事件始终继续，短按不缓存。

判定采用 Active 硬门后的实时形状查询，Active 起点清每挥击 HashSet，排除自身。木桩独立 StatusEffects，旧硬直每帧消费距离/N并递减，第N次消费后到期；新命中替换剩余位移与时长，MoveAndCollide挡墙。几何木桩直接画白，闪白时钟与相机同冻；玩家动画仍手动物理推进。相机 ManualAdvance 默认关闭，仅此场景显式驱动。机器覆盖与偏离见 [GP-13](./issues/issue-GP-13-hit-detection-feedback.md)。

以下保留流程意图；类型与成员以现行实现为准：

```
if hitstop.Tick(): return
player.AdvanceCombat()
dummy.AdvanceCombat()
camera.Advance(delta)
hitbox.Resolve(player, reaction => {
    hitstop.Begin(reaction.HitstopFrames)
    if reaction.IsHeavy: camera.Rig.Shake()
})
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

GP-13图形入口保留原34标签并新增22项输入恢复判据，共56项。跳/轻击/重击各自从可接受动作的待机态主动Begin(5)：F1末按下、F2核按住并松开、F3至F5核释放，R1至R8逐帧无重放，R9新按阳性对照。冲刺按右+冲刺，冻结5帧不动；恢复逐帧核Dash、规则/引擎横速与实际位移（1040/60每帧加速，夹紧176），R12后松冲刺按1560/60减至104并维持普通移动，再松方向停稳。原真实命中阶段仍查轻3/重5的状态、动画及相机冻结；独立阶段不冒充命中动作中的恢复。入口对全部标签严格核名/数量/摘要，新增22项各做缺失与FAIL日志自证，连原11项共55。

| US／FR | 测试 | 类型 | 说明 |
| --- | --- | --- | --- |
| `US-001`/`FR-4` | 运动学纯函数 | 单元 | 移动/跳/重力；手感「跟手」实机 |
| `US-001`/`FR-23,24`／`FR-28`（速度） | 纵深钳制、连续性、空中锁与落地解锁、三轴不串；两个纵深速度在 `CombatFeel` 且一次纵深闪避走不完整条带 | 单元＋图形探针 | 单测钉三轴分离，`player_dev.py` 的 4 条钉引擎接线；速度是未校准初值归 `GP-6`，48px 够不够归 `ENG-16` |
| `FR-26,27` | 纵深排序两键、绘制偏移、影子的位置与随高度缩放 | 单元＋图形探针 | `DepthRenderingTests` 12 条钉规则，`depth_dev.py` 13 条钉引擎（含截图数像素证明前后关系真的交换）；影子四个初值归 `GP-6`，满编可读性归 `ENG-16` |
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
- **已核对**：samurai 表只有 idle 10、run 16、attack1 7、hurt 4 帧，均 96×96；跳跃、闪避、重击及轻击后续段缺图，GP-12 明显几何占位，不宣称完整动画覆盖。**已被 `ART-6` 取代**：主角现在用作者自绘的七张表（统一帧框 46×32、锚点第 23 列、地面行第 30 行），缺图几何占位机制保留但当前无动作走它；`hit`／`defense`／`death` 入仓但刻意不载（有图没规则）。
- **已验证（ART-6）**：引擎侧逐像素核过七张表 54 帧的脚底行都是第 29 行、本体最高 30px（≤32px 铁律）、188 个物理帧里精灵帧与规则相位逐帧一致；同一距离轻击打空而重击打到，证明判定框真的按轻重换尺寸而不只是常量分开了。详见 [`issue-ART-6`](./issues/issue-ART-6-role-action-frames.md)。
- **已验证（GP-13）**：真实命中后另开落地待机主动顿帧阶段，跳/轻击/重击分别在冻结期完整按放，恢复首帧及随后8帧不重放，之后新按键可起动作。方向+冲刺覆盖冻结5帧零位移、首恢复帧速度与位移、逐帧加速至176、松冲刺减至104普通移动及松方向停稳。输入均deferred注入并经InputRouter读取，保留最后冻结帧Remaining=0仍跳过的语义；仅手感与缺图仍待人工。
