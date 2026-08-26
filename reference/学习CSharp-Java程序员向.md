---
type: reference
status: active
owner: project
last_verified: 2026-08-10
---

# C# 语法与惯用法（写给 Java 程序员）

> **目的**：本项目以 C# 编写 Godot 游戏，基线为 `net10.0` + `LangVersion=latest`（对应 C# 14），见 [ADR-0005](../decisions/ADR-0005-技术基线.md)。你有 Java 基础，很多概念相通，但 C# 有一批 Java 没有、或写法不同的语法与惯用法。本文对照 Java 说明差异。
>
> **怎么用**：读代码遇到看不懂的写法，来这里查。这是活文档 —— 碰到新写法就补一条。
>
> **继承说明**：本文继承自前作《火种》，当时基线是 C# 12 / .NET 8。文中示例的语法在 C# 14 下全部仍然有效；**C# 13 与 14 新增的特性尚未补入**，见[待办台账](../spec/issues/README.md) `DOC-1`。示例中引用的类名来自前作代码，新代码仓建立后需替换为真实示例。
>
> **配套**：命名与风格规范以代码仓 `CONVENTIONS.md` 为准（待 `ENG-4` 建立）。

---

## 目录

1. [命名空间与 using（对照 Java 的 package/import）](#一命名空间与-using)
2. [属性 Property（C# 最该先懂的东西）](#二属性property)
3. [表达式体成员 `=>`（一行方法/属性）](#三表达式体成员-)
4. [可空引用类型 `?` 与 `!`（告别 NullPointerException）](#四可空引用类型--与-)
5. [null 相关运算符：`?.` `??` `??=`](#五null-相关运算符)
6. [switch 表达式与模式匹配](#六switch-表达式)
7. [集合初始化 / 对象初始化器](#七集合初始化--对象初始化器)
8. [LINQ（对应 Java Stream）](#八linq相当于-java-stream)
9. [委托与事件：`Action` / `event`（对照 Java 接口回调）](#九委托与事件action--event)
10. [enum / 记录式属性 `init` / 元组](#十enum--init--元组)
11. [其他小语法：`var`、字符串插值、`const`、`out`、模式匹配](#十一其他小语法)
12. [命名约定差异（C# vs Java）](#十二命名约定差异)
13. [继承与多态：`abstract` / `virtual` / `override` / `: base()`](#十三继承与多态)
14. [struct 值类型 vs class 引用类型](#十四struct-值类型-vs-class-引用类型)
15. [运算符重载 + 重写 Equals/GetHashCode/ToString](#十五运算符重载--重写-object-方法)
16. [静态类 static class（工具类/图鉴）](#十六静态类-static-class)
17. [特性 Attribute（对照 Java 注解）+ 泛型方法](#十七特性-attribute--泛型方法)
18. [当前项目还使用的语法](#十八当前项目还使用的语法)

---

## 一、命名空间与 using

**Java**：`package com.foo.bar;` + `import java.util.List;`
**C#**：`namespace Emberfall.Items;` + `using System.Collections.Generic;`

本项目例子（`Backpack.cs` 顶部）：

```csharp
using System.Collections.Generic;   // 相当于 import，引入 List<T> 等
using System.Linq;                  // 引入 LINQ 扩展方法（.Where/.FirstOrDefault…）

namespace Emberfall.Items;          // 文件级命名空间（C# 10+，末尾分号，无大括号）
```

**差异与好处**：
- C# 的 `namespace` 不强制对应文件夹路径（Java 的 package 强制）。本项目**约定**让它对应目录（`Emberfall.Items` ↔ `scripts/items/`），是团队规范而非语言强制。
- `using` 引入的是**命名空间**（一整个），不像 Java `import` 通常精确到类。所以 `using System.Collections.Generic;` 一次把 `List`、`Dictionary`、`HashSet` 全带进来。
- **文件级命名空间**（`namespace X;` 后面直接写代码，不用把整个文件缩进进大括号）是新语法，少一层缩进，本项目统一用它。

---

## 二、属性（Property）

这是 Java 程序员最需要先适应的东西。**C# 不写 getter/setter 方法，而是用"属性"**。

本项目例子（`ConsumableDef.cs`）：

```csharp
public string Id { get; }              // 只读属性（只有 get）
public int Count { get; set; }         // 可读可写
public int Capacity { get; set; }
```

**对照 Java**：你在 Java 里会写

```java
private final String id;
public String getId() { return id; }   // getter
// 可写的还要写 setter
```

C# 一行 `public string Id { get; }` 就等价于"私有字段 + getter"。**调用时也不写括号**：

```csharp
bag.Capacity        // C#：像访问字段一样，实际走属性
bag.getCapacity()   // Java 风格，C# 里没有
```

**几种常见形态（本项目都有）**：

```csharp
// 1) 自动属性：编译器自动生成隐藏字段
public int Count { get; set; }

// 2) 只读自动属性：只能在构造函数里赋值（相当于 Java 的 final 字段 + getter）
public string Id { get; }

// 3) private set：外部只读、类内部可改（封装的关键）
public int InnerDemon { get; private set; } = 0;   // 还能给默认值

// 4) 计算属性（get 里写逻辑，没有存储字段）——见下一节
public bool IsFull => UsedSlots >= Capacity;

// 5) init：只能在对象初始化时赋值，之后只读（见第十节）
public string Label { get; init; } = "";
```

**好处**：
- 封装成本极低——先写 `{ get; set; }`，将来要加校验/通知，改成 `{ get; private set; }` + 手写逻辑即可，**调用方代码不用改**（Java 里从字段改成 getter 是破坏性变更）。
- 本项目大量用 `{ get; private set; }` 做"外部只读、内部可控"，比如 `Combatant.CurrentHp`——外部能看血量，但只能通过 `TakeDamage()`/`Heal()` 改，防止乱赋值。

---

## 三、表达式体成员 `=>`

当一个方法/属性的实现只有"返回一个表达式"时，可以用 `=>`（读作"goes to"）写成一行。**注意这里的 `=>` 不是 lambda，是方法体的简写**。

本项目例子：

```csharp
// 计算属性（无存储字段，每次访问都算）
public int UsedSlots => _stacks.Count;
public bool IsFull => UsedSlots >= Capacity;
public bool Has(string id) => CountOf(id) > 0;

// 表达式体方法
public void Clear() => _stacks.Clear();
public static TalentDef? Get(string id) => _all.Find(t => t.Id == id);
```

**对照 Java**：Java 没有这个。你得写

```java
public int getUsedSlots() { return stacks.size(); }
```

**好处**：短小的取值/转发方法一行搞定，读起来像"定义即等式"。本项目里大量的 `X => ...` 都是这种简写。

**易混点**：`=>` 有两个含义，靠上下文区分：
- 成员定义处（`public int Foo => ...;`）＝方法体简写。
- 参数列表后（`s => s.Id == id`）＝lambda 表达式（匿名函数），见第八节。

---

## 四、可空引用类型 `?` 与 `!`

本项目开了 `<Nullable>enable</Nullable>`。它让编译器分析引用是否可能为空并给出警告；Java 通常依靠 `@Nullable`、静态分析工具或 `Optional`。这是一层编译期检查，不是绝对的运行时保证。

规则：**默认引用类型不可为 null**；要允许 null，得在类型后加 `?`。

本项目例子：

```csharp
// String? = 可能为 null 的字符串；编译器会检查你有没有判空
public string? Description { get; }
public string? EffectTag { get; }

// TalentDef? = 可能返回 null（找不到就 null）
public static TalentDef? Get(string id) => _all.Find(t => t.Id == id);

// StudentRecord? 参数，调用方可能传 null
private void ShowSkillLoadoutFor(StudentRecord? s)
{
    if (s == null) { ...; return; }   // 编译器要求你先判空才能用 s
    ...
}
```

**`!` 是"我确定不为 null"运算符（null-forgiving）**，压制编译器警告：

```csharp
public static EventBus Instance { get; private set; } = null!;
// = null! 意思："我知道现在是 null，但我保证用之前会赋值，别警告我"
// 本项目 Autoload 单例常这么写：字段在 _EnterTree() 里赋值，构造时先占位 null!

var skill = SkillCatalog.LearnableSkill(id, sid);
if (skill != null) kai2.LearnSkill(skill);   // 判空后再用
```

**好处**：把“可能为 null”写进类型信息，编译器能提醒未处理的路径，大幅减少运行时空引用。`!`、反射、外部输入或不完整初始化仍能绕过检查，因此边界处仍要校验。

---

## 五、null 相关运算符

三个高频糖，本项目到处用：

### `?.` 空条件访问（safe navigation）

```csharp
// 若 FirstOrDefault 返回 null，整个表达式就是 null，不会抛异常
_stacks.FirstOrDefault(s => s.Def.Id == id)?.Count
```

对照 Java：Java 没有同名的空条件访问运算符，通常写三元判空或用 `Optional.map(...)`。

### `??` 空合并（null-coalescing）

```csharp
// 左边不为 null 就用左边，否则用右边（默认值）
_defs.TryGetValue(id, out var factory) ? factory() : ...
Description ?? AutoDescription       // 有手写描述用手写，否则用自动生成
rng ?? Rng.Volatile()                // 传了随机源就用，否则走项目统一随机入口
```

`?. ` 和 `??` 常连用：

```csharp
public int CountOf(string id) => _stacks.FirstOrDefault(s => s.Def.Id == id)?.Count ?? 0;
// 找不到那一格 → ?. 得到 null → ?? 兜底为 0。一行完成"找不到就返回0"。
```

对照 Java：`Optional.ofNullable(x).map(...).orElse(0)` 或一堆三元运算符。C# 一行 `a?.b ?? c` 更直观。

### `??=` 空合并赋值（懒初始化）

```csharp
// 若 _station 为 null，才创建并赋值（相当于懒加载）
_station ??= StationRosterFactory.CreatePlaceholder(TarYear, TarDayOfYear);
```

等价于 `if (_station == null) _station = ...;`。本项目 `GameState.Station` 用它做懒创建。

---

## 六、switch 表达式

C# 的 `switch` **可以当表达式用**（直接返回值），比 Java 传统 switch 强太多，本项目极其常用。

本项目例子（`Skill.cs`）：

```csharp
string kindName = Kind switch
{
    SkillKind.Melee  => "近战",
    SkillKind.Ranged => "远程",
    SkillKind.Spell  => "法术",
    SkillKind.Support => "辅助",
    SkillKind.Move   => "位移",
    _ => "技能",        // _ 是 default（必须覆盖所有情况，否则编译警告）
};
```

**对照 Java**：Java 14+ 有 `switch` 表达式（`case X -> ...`），比较接近了；但 C# 的更早、且能配**模式匹配**：

```csharp
// 按数值区间匹配（Java 做不到这么简洁）
public InnerDemonState InnerDemonState => InnerDemon switch
{
    >= 80 => InnerDemonState.Broken,    // 关系模式：>= 80
    >= 40 => InnerDemonState.Shaken,
    _ => InnerDemonState.Calm,
};

// 类型 + 条件匹配
public bool UsableInBattle => Scene is ConsumableScene.BattleOnly or ConsumableScene.Both;
//                                    ^^ is + or 模式：等价于 == BattleOnly || == Both
```

**好处**：
- "输入 → 输出"的映射（枚举转中文名、档位判定）写得像一张表，清晰无遗漏。
- 编译器检查完整性——漏了分支会警告。
- `_`＝默认分支；`>= 80`＝关系模式；`A or B`＝或模式；`is`＝类型/常量模式。这些叫**模式匹配（pattern matching）**，Java 才刚开始有。

---

## 七、集合初始化 / 对象初始化器

**对象初始化器**：new 的时候直接用 `{ }` 给属性赋值，不用写一堆 setter 调用。

本项目例子：

```csharp
var boss = new Combatant("boss_0", "深渊首领", Faction.Enemy,
    maxHp: 160, attack: 20, defense: 9, speed: 11) { SlotIndex = 0 };
//                                                  ^^^^^^^^^^^^^^^ 构造后顺手设属性

var btn = new Button
{
    Text = "出征 →",
    Disabled = !usable,
    SizeFlagsHorizontal = SizeFlags.ExpandFill,   // 逗号分隔的属性赋值
};
```

**集合初始化器**：

```csharp
private readonly List<ItemStack> _stacks = new();  // new() 目标类型推断，见下

var builders = new Func<string, RationProposal>[]  // 数组初始化
{
    EliteDemand, MondCut, SerinFavor, ChildRation,
};

Choices =           // 嵌套：给集合属性直接塞元素
{
    new RationChoice { Label = "…", Materials = 25 },
    new RationChoice { Label = "…", Crystal = 2 },
},
```

`maxHp: 160` 这种叫**具名参数**（named argument）——调用时写出参数名，可读性高、还能跳过中间的可选参数。Java 完全没有，只能靠参数顺序或 Builder 模式。

`new()`（不写类型）叫**目标类型 new**：左边已声明类型时，右边不用重复写。`List<ItemStack> _stacks = new();` 等价 `= new List<ItemStack>();`。

---

## 八、LINQ（对应 Java Stream）

LINQ 是 C# 的集合查询，和 Java Stream 思路相近。多数集合可直接调用 LINQ 扩展方法；需要具体列表时用 `.ToList()`。

本项目例子：

```csharp
// 过滤（Java: .stream().filter(...)）
Skills.Where(s => !s.IsPassive)

// 找第一个匹配的，找不到返回 null/default（Java: findFirst().orElse(null)）
_stacks.FirstOrDefault(s => s.Def.Id == def.Id)
_all.Find(t => t.Id == id)              // List 自带的 Find，同理

// 投影/转换（Java: .map(...)）
s.ItemStock.Stacks.Select(st => (st.Def.Id, st.Count))

// 排序（Java: .sorted(...)）
_all.Where(t => ...).OrderBy(t => t.Branch).ThenBy(t => t.Tier)

// 判断存在/全部（Java: anyMatch / allMatch）
bag.Stacks.Any(s => s.Def.UsableInBattle)
normal.Enemies.All(e => !e.Id.StartsWith("elite"))

// 计数、求和、转列表（Java: count()/sum()/collect(toList())）
_deployChecks.Values.Count(c => c.ButtonPressed)
_equipped.Values.Sum(selector)
learnable.ToList()
```

**关键差异**：

- Java 常以 `.collect(Collectors.toList())` 收集结果；C# 对应用 `.ToList()`。两者的性能都取决于元素类型与查询链，不能仅凭语法判断是否发生装箱。
- `FirstOrDefault` / `SingleOrDefault`：找不到时返回该类型的默认值（引用类型是 null，int 是 0），不像 Java 返回 `Optional`。本项目常配 `?.` `??` 处理找不到的情况。
- `s => s.Id == id` 就是 **lambda**（匿名函数），跟 Java `s -> s.getId().equals(id)` 一样，只是箭头是 `=>`、比较用 `==`（字符串比较后面讲）。

⚠️ **字符串比较**：C# 里 `==` 对 `string` 是**比较内容**（值相等），不像 Java 的 `==` 比引用！所以 `s.Def.Id == id` 是对的，不用 `.equals()`。（Java 程序员最容易在这里踩反——Java 要 `.equals()`，C# 直接 `==`。）

---

## 九、委托与事件：`Action` / `event`

这是本项目**逻辑层↔表现层解耦**的核心机制。Java 里你会用接口（如 `OnClickListener`）做回调；C# 用**委托（delegate）**，`Action`/`Func` 是内置的通用委托类型。

### `Action` / `Func`：把"方法"当值传

```csharp
// Action<T> = 接收 T、无返回值的函数（相当于 Java Consumer<T>）
public event Action<int>? ItemUsesChanged;

// Func<T, TResult> = 接收 T、返回 TResult（相当于 Java Function<T,R>）
private static readonly Dictionary<string, Func<List<Skill>>> _studentSkills = ...;
//                                          ^^^^ 值是"无参、返回 List<Skill>"的函数

// System.Action 无参无返回（相当于 Java Runnable）
private void AddSubEntry(..., System.Action onPressed) { ... }
```

对照 Java：Java 8 的 `Consumer` / `Function` / `Runnable` / `Supplier` 一一对应，只是 C# 统一叫 `Action`（无返回）和 `Func`（有返回，最后一个泛型参数是返回类型）。

### `event`：观察者模式的语言级支持

本项目 `BattleManager`（逻辑层，不碰 UI）用 event 向外通知：

```csharp
// 声明事件（?表示可空，即可能没人订阅）
public event Action<Combatant, Combatant, int>? DamageDealt;
public event Action<int>? ItemUsesChanged;

// 触发（?. 保证没人订阅时不抛空指针）
ItemUsesChanged?.Invoke(ItemUsesRemaining);
DamageDealt?.Invoke(user, target, dealt);
```

表现层订阅（`+=`）和解绑（`-=`）：

```csharp
_station.TimeAdvanced += OnTimeAdvanced;    // 订阅（+= 加一个处理器）
_station.TimeAdvanced -= OnTimeAdvanced;    // 解绑（-= 移除）
```

**对照 Java**：Java 没有语言级 event，你得自己维护 `List<Listener>` + `addListener/removeListener` + 遍历调用。C# 的 `event` 把这套内建了：`+=` 加订阅、`-=` 退订、`?.Invoke(...)` 广播。

**本项目铁律**：逻辑层用 `event` 单向通知表现层，实现规则与画面分离。跨场景订阅必须解绑，详见代码仓库 `CONVENTIONS.md` §7.2；统一用 `SubscriptionBag` 成对登记。具名方法最容易解绑；lambda 也可以，但必须保存并传回**同一个委托实例**，不能在 `-=` 时临时再写一个外观相同的新 lambda。

---

## 十、enum / init / 元组

### enum（枚举）

跟 Java 类似，但 C# 枚举底层就是整数，更轻量：

```csharp
public enum ConsumableScene { BattleOnly, ExploreOnly, Both }

// 强转与整数互通（Java 枚举不能直接转 int）
public static int MaxAffixes(EquipmentRarity r) => (int)r;  // 枚举转 int
RationStance stance = (RationStance)data.RationStance;      // int 转枚举（存档回灌）
```

对照 Java：Java 枚举是"功能完整的类"（能带方法/字段），C# 枚举默认只是命名整数（更接近 C 的 enum）。本项目要给枚举配数据时，用**静态工具类 + switch 表达式**（如 `EquipmentRarityUtil.Name(r)`），而不是像 Java 那样在枚举里塞方法。

### `init` 属性（不可变对象的优雅写法）

```csharp
public sealed class RationChoice
{
    public string Label { get; init; } = "";     // 只能在对象初始化时赋值
    public int Materials { get; init; }
}

// 用起来：初始化时能设，之后就只读
new RationChoice { Label = "据理力争", Materials = 25 }
choice.Materials = 5;   // ❌ 编译错误：init 属性初始化后不可改
```

对照 Java：类似 Java 的 `final` 字段，但 `init` 配合对象初始化器，比 Java 的"全参构造函数 / Builder"简洁得多——既保证不可变，又不用写一堆构造参数。`sealed`＝不可被继承（相当于 Java 的 `final class`）。

### 元组（Tuple）：临时打包多个值，不必定义类

```csharp
// 返回两个值，不用专门定义一个类
public (int crystal, int tech) MonthlyBonusFor => ...;
(int crystal, int tech) = Resources.MonthlyBonusFor;   // 解构接收

// List 里存元组
public List<(string tag, int power)> PendingStartEffects { get; } = new();
foreach (var (tag, power) in unit.PendingStartEffects) { ... }  // 遍历时解构
```

对照 Java：Java 没有原生元组（要么定义类，要么用 `Map.Entry`/第三方 `Pair`）。C# 的具名元组 `(int crystal, int tech)` 轻量、带名字、能解构，适合"临时返回几个值"。

---

## 十一、其他小语法

### `var`：局部变量类型推断

```csharp
var stack = _stacks.FirstOrDefault(...);   // 编译器推断 stack 是 ItemStack
var dialog = new AcceptDialog { ... };
```

跟 Java 10 的 `var` 一样，只能用于局部变量。本项目在右侧类型或变量语义清楚时使用 `var`，包括 `new`、工厂和查询调用；数值类型与语义不明的返回值写显式类型。字段、属性和参数仍声明明确类型。

### 字符串插值 `$"..."`

```csharp
Log($"向行商购得「{offer.Def.DisplayName}」（灵材 -{offer.PriceEssence} → {Essence}）。");
// {} 里直接写表达式，还能带格式：
$"契合{s.EffectiveAffinity:P0}"      // :P0 = 百分比、0位小数（0.85 → "85%"）
$"攻击{PassiveAttack:+0;-0}"          // 带符号：正数显示 +3、负数 -3
$"魔蚀{m.MagicErosion:P0}"
```

对照 Java：Java 常用 `+`、`String.format(...)` 或 `"%s".formatted(...)`；文本块解决多行字面量，不等同于字符串插值。C# 的 `$"{x}"` 可直接嵌入表达式，`:P0`、`:+0;-0` 等是**格式说明符**。

### `const` 与 `static readonly`

```csharp
public const int ItemUsesPerBattle = 6;             // 编译期常量（Java: static final 基本类型）
private static readonly int[] AllSlots = { 0,1,2,3 };  // 运行期只读（引用类型用这个）
```

`const` 只能用于编译期能定死的值（数字/字符串）；对象/数组用 `static readonly`（相当于 Java `static final`）。

### `out` 参数：一个方法"返回"多个结果

```csharp
if (_defs.TryGetValue(id, out var factory))   // 找到则 factory 被赋值、返回 true
    return factory();
```

`out` 表示"这个参数由方法内部赋值传出"。`TryGetValue` 是 C# 字典的惯用法：返回 bool 表示有没有、`out` 参数带出值——比 Java 的"先 containsKey 再 get"少一次查找。`out var factory` 是就地声明变量。

### 模式匹配 `is`

```csharp
if (_currentEvent is not { Kind: ExpeditionEventKind.WanderingMerchant }) return false;
// is + 属性模式：判断"是商人事件"，not 取反
if (Commander is { } cmd && cmd.IsAlive)   // { } 模式：非 null 时把它赋给 cmd
```

对照 Java 16+ 的 `if (obj instanceof String s)`（类型 + 绑定变量），C# 的 `is` 更早且更强（能匹配属性、区间、null）。

---

## 十二、命名约定差异

C# 和 Java 命名习惯不同（本项目严格遵循 C# 官方，见 `CONVENTIONS.md`）：

| 元素 | Java 习惯 | C# 习惯（本项目） | 例子 |
| --- | --- | --- | --- |
| 类/接口 | PascalCase | PascalCase（一致） | `BattleManager` |
| **方法** | camelCase | **PascalCase** | `TakeDamage()` 而非 `takeDamage()` |
| **属性/公有成员** | camelCase(getter) | **PascalCase** | `CurrentHp` 而非 `getCurrentHp()` |
| 局部变量/参数 | camelCase | camelCase（一致） | `int slotIndex` |
| **私有字段** | camelCase | **`_camelCase`（下划线前缀）** | `_stacks`、`_rng` |
| 常量 | UPPER_SNAKE | PascalCase | `ItemUsesPerBattle` 而非 `ITEM_USES` |
| 接口 | 无前缀 | **`I` 前缀** | `IReadOnlyList`（Java 里就叫 List） |
| 大括号 | 行尾 `{` | **另起一行（Allman）** | 见下 |

大括号风格（本项目用 Allman，`{` 单独一行）：

```csharp
public int Add(ConsumableDef def, int amount = 1)
{                                    // ← { 另起一行
    if (amount <= 0) return 0;
}
```

Java 通常是 `public int add(...) {`（`{` 跟在行尾，K&R 风格）。**这只是风格差异，不影响功能**，但本项目统一 Allman（Godot 官方 C# 规范）。

---

## 十三、继承与多态

本项目 `StatusEffect`（战斗状态）是典型：一个抽象基类 + 一堆子类。

### `abstract`

```csharp
public abstract class StatusEffect { public string Id { get; } }
```

和 Java 的 `abstract class` 完全一样：不能直接 new，只能被继承。

### `virtual` / `override`（与 Java 最大的差异）

Java 方法**默认可重写**（除非 `final`）；**C# 默认不可重写，基类要显式加 `virtual`，子类重写要加 `override`**。

```csharp
// 基类：virtual = 允许子类重写，给了默认实现
public virtual int ModifyIncomingDamage(int baseDamage, Combatant owner, Combatant attacker) => baseDamage;

// 子类 ShieldStatus：override = 我在重写（护盾吸伤）
public override int ModifyIncomingDamage(int baseDamage, Combatant owner, Combatant attacker)
{
    if (ShieldAmount <= 0) return baseDamage;
    // ...
}
```

**好处**：基类主动声明"可被重写"、子类主动声明"我在重写"，比 Java"默认全可重写"更防误改，编译器还校验签名匹配。Java 的 `@Override` 是可选注解；C# 的 `override` 是强制关键字。

### `: base(...)`（调父类构造函数）

```csharp
public CorruptionStatus(int stacks = 1, int duration = 3, Combatant? source = null)
    : base("corruption", "魔蚀侵染", "每回合受伤", StatusType.Debuff, stacks, maxStacks: 10, duration, source)
{ }   // 函数体空，活都在 base(...) 里干完了
```

Java 是在构造体内第一行 `super(...)`；C# 是在参数列表后 `: base(...)`，位置不同、作用相同。

---

## 十四、struct 值类型 vs class 引用类型

Java 只有引用类型（基本类型 int/double 除外）。**C# 有 `class`（引用类型）和 `struct`（值类型）两种自定义类型**。本项目 `HexCoord`/`CommanderCommand`/`ExpeditionParty` 是 `readonly struct`：

```csharp
public readonly struct HexCoord : IEquatable<HexCoord>
{
    public int Q { get; }
    public int R { get; }
    public HexCoord(int q, int r) { Q = q; R = r; }
}
```

| | class 引用类型 | struct 值类型 |
| --- | --- | --- |
| 赋值/传参 | 传引用（改一个影响另一个） | **传拷贝**（改拷贝不影响原件） |
| 默认值 | `null` | 全字段零值（不会 null） |
| 相等 | 默认比引用 | 默认比字段值 |
| Java 对应 | 普通类 | Java 没有（最近似 `record` 但仍是引用类型） |

**为什么 HexCoord 用 struct**：坐标是"小而不可变的值"，像 `int` 一样按值传最自然，没必要共享同一个坐标对象。**判断口诀**：要共享/会变/有身份 → class（如 Combatant/StudentRecord）；轻量/不可变/是值 → struct（坐标/向量）。`readonly struct` = 全字段只读，值类型最佳实践。

---

## 十五、运算符重载 + 重写 object 方法

**Java 不能重载运算符**；C# 可以。`HexCoord` 重载了 `==`/`!=` 并重写了 Equals/GetHashCode/ToString：

```csharp
public bool Equals(HexCoord other) => Q == other.Q && R == other.R;
public override bool Equals(object? obj) => obj is HexCoord other && Equals(other);
public override int GetHashCode() => HashCode.Combine(Q, R);        // ≈ Java Objects.hash(q,r)
public static bool operator ==(HexCoord a, HexCoord b) => a.Equals(b);  // Java 没有
public static bool operator !=(HexCoord a, HexCoord b) => !a.Equals(b);
public override string ToString() => $"({Q},{R})";                  // ≈ Java toString()
```

- `Equals`/`GetHashCode`/`ToString` 对应 Java 的 `equals`/`hashCode`/`toString`，**规矩一样**：重写 Equals 就必须重写 GetHashCode（否则进 HashSet/Dictionary 出错）。
- `operator ==` 让 `coordA == coordB` 按值比较（否则 class 的 == 比引用）。
- `IEquatable<HexCoord>` 提供强类型 Equals，避免值类型比较的装箱开销，是 struct 最佳实践。
- ⚠️ 运算符重载慎用，只在语义确为值比较/运算时用（坐标/向量/金额）。

---

## 十六、静态类 static class

本项目大量目录、工厂和工具是 `static class`（`SkillCatalog`、`TalentCatalog`、`EquipmentCatalog`、`ConsumableCatalog`、`RelicCatalog`、`EquipmentRarityUtil`）：

```csharp
public static class TalentCatalog
{
    private static readonly List<TalentDef> _all = BuildAll();
    public static TalentDef? Get(string id) => _all.Find(t => t.Id == id);
}
```

`static class` = 不能 new、只能装静态成员的"函数与常量容器"，调用直接 `TalentCatalog.Get(...)`。对照 Java：Java 顶层类没有 `static` 修饰，你得写"全 static 方法 + 私有构造防实例化"的工具类（如 `Collections`）；C# 一个 `static class` 关键字表达此意图，编译器强制无实例成员、不可 new。本项目图鉴是"无状态查表逻辑"，用 static class 最贴切。

---

## 十七、特性 Attribute + 泛型方法

### 特性（Attribute）≈ Java 注解

`[Xxx]` 对应 Java `@Xxx`，给代码贴元数据供框架读取。存档 `SaveData.cs`：

```csharp
[JsonPropertyName("protagonistAlias")]   // ≈ Jackson @JsonProperty
public string ProtagonistAlias { get; set; } = "";
```

**好处**：重命名 C# 属性后，只要 JSON 键名不变，旧存档仍能读（保护兼容性）。

Godot 特性：

```csharp
[GlobalClass] public partial class StudentDef : Resource { ... }  // 编辑器识别为资源类型
[Export] public int BaseCapacity { get; set; } = 10;              // 暴露到检视器可编辑
```

### `partial`

```csharp
public partial class GameState : Node { ... }
```

`partial` = 类定义可拆在多处、编译时合并。本项目 Godot 节点类都是 `partial`——因为 **Godot 的 C# 源生成器会自动生成另一半**（信号绑定等）和你这半合并。Java 没有（一个类必须写在一个文件里）。

### 泛型方法

```csharp
private static void Shuffle<T>(IList<T> list, Random rng) { ... }   // <T> 在方法名后
```

同 Java `static <T> void shuffle(...)`，只是 `<T>` 位置不同。C# 泛型在运行时保留足够的类型信息，并允许 `List<int>` 直接使用值类型；Java 泛型采用类型擦除，基本类型需写成包装类 `List<Integer>`。

---

## 十八、当前项目还使用的语法

除前文内容外，当前代码还使用下面几种写法：

**`yield return`：惰性序列迭代器。** `StationManager.LearnableSkillsFor`、`EquipmentLoadout.FunctionalAffixes` 等入口会逐个产生结果：

```csharp
public IEnumerable<Skill> LearnableSkillsFor(string studentId)
{
    var rec = FindStudent(studentId);
    if (rec == null) yield break;                    // 提前结束序列
    foreach (var sk in SkillCatalog.LearnableSkillsFor(studentId))
        if (!rec.HasSkill(sk.Id)) yield return sk;   // 逐个产出、不一次性建列表
}
```

`yield return` = 惰性生成序列（遍历到哪算到哪），`yield break` 提前终止。相当于 Java 手写 `Iterator` 或 Stream 惰性求值，被语法糖化。

- **`async` / `await`**：异步等待计时器或帧信号，例如 `AudioManager`、`BattlePresentationDirector`、`SceneSmoke`；等待期间不阻塞主线程。
- **`using` 与 `IDisposable`**：作用域结束时自动释放资源；`using (Core.Perf.Measure(...))` 用它结束计时。
- **扩展方法**：给现有类型增加调用形式；`DialogUtil.Present(this AcceptDialog ...)` 让弹窗可写成 `dialog.Present(parent)`。
- **局部函数**：在方法内部声明只供该流程使用的函数；弹窗常用 `void Rerender()` 收拢重绘步骤。
- **`record` / `record struct`**：按数据值表达相等性的简洁类型；项目目录定义中已有多处使用。

---

## 附：读本项目代码的建议路径

1. 先读一个**纯逻辑小类**感受属性/表达式体/LINQ：`scripts/items/Backpack.cs`。
2. 再读**枚举 + switch 表达式**：`scripts/combat/Skill.cs` 的 `AutoDescription`。
3. 读**事件解耦**：`scripts/combat/BattleManager.cs` 的 `event` 声明 + `?.Invoke`，对照 `scenes/combat/BattleScene.cs` 的 `+=` 订阅。
4. 读**空安全实战**：`scenes/station/StationScene.Muster.cs` 的 `SelectedStudent()` 返回 `StudentRecord?` 后如何判空。

遇到不认识的写法，先回本文查；查不到就往本文补一条（活文档）。
