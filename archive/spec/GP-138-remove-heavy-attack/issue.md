---
type: workdoc
status: archived
owner: project
last_verified: 2026-10-27
---

# GP-138：删掉重攻击，只留轻攻击

> **历史背景·非依据。只读归档件，不得作为现行依据。** 现行事实的落点列在[待办台账](../../../spec/issues/README.md)「已归档编号」里 `GP-138` 那一行；剩余动作也在台账，不在本页。

## 目标

角色的普攻只剩轻攻击一种：重攻击的按键、动作与挂在它上面的规则全部删掉，**轻击打中才续段的那条连招照旧**。

## 来源

- 需求文档：同目录 [`prd.md`](./prd.md)，用户故事、功能需求与待确认问题都在那一份，本条不复述。
- 在敌人回到技能那张表那一轮（`GP-137`）定下：不需要重攻击，只有轻攻击；轻攻击一定时间内连续打中仍然有连招。

## 依赖

无编号依赖。需求文档已确认，几处取舍的答案写在它的正文里：打崩之后落在击倒与倒地追打上；命中反应的轻重留两组、改成一招自己的一格；键鼠 `K` 空着，手柄上面键只在按住扳机时当技能位；本份排在界面素材与作物素材那两份需求前面。

## 范围

**设计仓**

- 正典：[战斗与关卡 · 按键与连击](../../../canon/gameplay/战斗与关卡.md)那一行按键、[战斗与关卡 · 打击反馈](../../../canon/gameplay/战斗与关卡.md)击退与震屏两条、[战斗与关卡 · 防御与失衡](../../../canon/gameplay/战斗与关卡.md)那句「可被重击」、[角色与成长 · 四项属性的作用方向](../../../canon/gameplay/角色与成长.md)那条循环与它的代价、[玩法定位](../../../canon/gameplay/玩法定位.md)里写着「轻重攻击」的两处。改完要 `--repin`。
- 系统文档：[`角色动作状态系统`](../../../design/角色动作状态系统.md)攻击那一条、流转表「攻击·地面」那一行、免疫失衡那一段的代价与理由里那份通用状态清单；[`数值模型`](../../../design/数值模型.md)招式倍率那张表（`move_multipliers.protagonist_heavy`、`move_multipliers.student_heavy`）与判据 C4 的量测点；[`界面系统`](../../../design/界面系统.md)提到重击的一处；提案[`键鼠技能位挪到右手`](../../../design/proposals/键鼠技能位挪到右手.md)（`UI-14` 要按的清单在它里面）。
- 参考与制作：`reference/godot/输入.md`、`reference/godot/粒子着色器与音频.md`、`reference/踩坑记录.md`、`production/像素绘制原则.md` 各有一两处。
- 条目文件：`ART-6`、`GP-14`、`UI-14` 那三份里提到重击的勾选框与说明。

**代码仓**

- 规则层：`rules/Combat/ComboStateMachine.cs`（重攻击那一种连段类型与它的缓冲）、`rules/Combat/CombatFeel.cs`（重攻击那一组常量）、`rules/Combat/CombatInput.cs`、`rules/Combat/ActorCombatState.cs`、`rules/Combat/HitResolution.cs`、`rules/UI/InputActions.cs`、`rules/UI/InputBindings.cs`、`rules/UI/CameraFeel.cs`、`rules/UI/CameraRig.cs`。
- 引擎层：`src/World/PlayerActor.cs`、`src/World/Hitbox.cs`、`src/World/HitSpark.cs`、`src/World/CombatAudio.cs`、`src/World/TrainingRoom.cs`、`src/Platform/LocalPlayerController.cs`。
- 测试：`tests/Combat/ComboStateMachineTests.cs`、`tests/Combat/CombatFeelTests.cs`、`tests/Combat/HitResolutionTests.cs`、`tests/Combat/ActorCombatStateTests.cs`、`tests/UI/CameraTests.cs`、`tests/UI/InputMappingTests.cs`；`CONVENTIONS.md` 里拿重击举的例子。
- 美术：测试角色那组重击帧由作者在 Godot 里撤掉。

**注意搜的时候分清两件事**：「重攻击」这个动作删了，受击那一档的「重」（`heavy_hit`、重的那一组反应量）留着。按字面搜「heavy」会把两者混在一起。

## 验收标准

- [x] 需求文档出草稿：同目录 [`prd.md`](./prd.md)。
- [x] 作者答完需求文档的待确认问题，它改成 `approved`。
- [x] 打崩之后补什么定下来，正典那条循环的理由换成新落点（击倒与倒地追打）。
- [x] 输入动作里没有重攻击，两套设备的绑定一起删；手柄上面键换成只在修饰键组合里用的动作，六个技能位一个不少；键位测试跟着改。
- [x] 规则层没有重攻击那一种连段：轻击打中才续、打空不续照旧（改写后的连段测试全绿）。
- [x] 命中反应按这一招的轻重取，轻击每一段都是轻；重的那一组反应量、震屏、火花与受击表留着且有测试。
- [x] 数值模型里那组重击倍率删掉，设计仓 `python tools/simulate_week.py --check-doc` 通过，C4 的实测比值不变。
- [x] 代码仓 `python tools/verify.py` 全过；设计仓 `python tools/check_docs.py` 0 FAIL。
- [x] **作者实机确认**：训练房里按 `J` 连打木桩，每一段都出、命中反馈与删之前的轻击一样；对着空气按 `J`，第一段打完不续；按 `K` 什么都不发生。
- [x] 归档时把「重攻击」登进设计仓 `tools/retired-names.json` 的退役术语 —— 本条与需求文档到那时已进 `archive/`，登了不会让它们自己报错。

## 实现笔记

### 设计决策

- **上面键的动作名叫 `modifier_only`**（代码仓 `rules/UI/InputActions.cs`）。修饰键组合靠动作名认出面键被按下，所以那个面键不能没有动作；它不是战斗动作，键鼠上登记成豁免。
- **连段类型整个删掉了**，不是只删掉重的那一个取值：只剩一种连段时，「类型」这一格只剩「在不在出招」一个意思，而那已经有 `IsAttacking`。
- **轻重成了一个独立的取值**（代码仓 `rules/Combat/HitResolution.cs` 的 `HitWeight`），命中反应只按它取；轻击三段共用一格，值在 `rules/Combat/CombatFeel.cs`，按段各填等普攻改成从角色定义读（`GP-18`）。
- **`K` 的符号从绑定表的枚举里删了**：不绑任何动作的键留一个符号，就是留一个看起来可绑的位（同一份文件里 D-pad 上下两向不加符号是同一个理由）。

### 偏离

- **正典「打击反馈」里震屏那一条顺带改了**：原文写「只给重击与特定事件」，而轻的微震早已实现并由作者实机确认过（`GP-20` 归档那一行、`GP-13` 那一行）。只把「重击」换个说法会把一条与现状相反的规则写得更牢，所以改成按轻重分两组的现行事实。
- **测试角色那张重击帧删了**（代码仓 `assets/self-drawn/test-role/` 里不再有 `heavy` 那一张），需求文档的非目标原写「不删素材文件」。删的理由：引擎侧已经不载入它，它却仍随导出进包。原画留在工作区 `art-source` 里；受击那张 `heavy_hit` 不动。
- **手柄那一半没有实机项**：条目原先把「按住扳机按上面键放得出技能」也列进实机确认，而引擎侧还没有响应技能位按下的代码（按住扳机时那一组格子会亮，按下去之后没有任何东西接），这一下在游戏里看不出来。映射由代码仓 `tests/UI/InputMappingTests.cs` 钉着；放得出技能那一下的实机跟技能落地（`GP-31`）走，记在台账那一行。

### 待确认

无。
