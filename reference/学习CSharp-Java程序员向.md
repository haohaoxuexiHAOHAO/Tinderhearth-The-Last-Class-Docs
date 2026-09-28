---
type: reference
status: active
owner: project
last_verified: 2026-09-28
---

# C# 语法与惯用法（写给 Java 程序员）

> **目的**：本项目以 C# 编写 Godot 游戏，基线为 `net10.0` + `LangVersion=latest`（对应 C# 14），见 [ADR-0005](../decisions/ADR-0005-技术基线.md)。你有 Java 基础，很多概念相通，但 C# 有一批 Java 没有、或写法不同的语法与惯用法。本文对照 Java 说明差异。
>
> **怎么用**：读代码遇到看不懂的写法，来这里查。这是活文档 —— 碰到新写法就补一条。
>
> **读法**：这里的语法在 C# 14 下全部有效，C# 13 与 14 的新增特性见 §19、§20。**代码块里的示例取自本仓，块首用注释注明出处文件**，签名与逻辑一字不改，只截与该语法相关的那几行。本仓还没用到的语法**写明「本仓暂无」并说清它将来落在哪**，不拿占位名假装有 —— 读者照占位名去搜会一个都搜不到。
>
> **配套**：命名与风格规范以代码仓 `CONVENTIONS.md` 为准。

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
13. [继承与多态：`override` 与接口（本仓没有基类层级）](#十三继承与多态)
14. [struct 值类型 vs class 引用类型](#十四struct-值类型-vs-class-引用类型)
15. [运算符重载 + 重写 Equals/GetHashCode/ToString](#十五运算符重载--重写-object-方法)
16. [静态类 static class（纯判定 / 常量表 / 查表）](#十六静态类-static-class)
17. [特性 Attribute（对照 Java 注解）+ 泛型方法](#十七特性-attribute--泛型方法)
18. [另外几种会遇到的写法](#十八另外几种会遇到的写法)

---

## 一、命名空间与 using

**Java**：`package com.foo.bar;` + `import java.util.List;`
**C#**：`namespace Tinderhearth.Rules.Economy;` + `using System.Collections.Generic;`

```csharp
// rules/Economy/CropDefinition.cs 的开头
using Tinderhearth.Rules.Foundation.Content;   // 相当于 import，引入 ContentJson

namespace Tinderhearth.Rules.Economy;          // 文件级命名空间（C# 10+，末尾分号，无大括号）
```

**差异与好处**：
- C# 的 `namespace` 不强制对应文件夹路径（Java 的 package 强制）。本项目**约定**让它对应目录，是团队规范而非语言强制；命名空间怎么排在代码仓 `ARCHITECTURE.md` 那张表，风格口径在 `CONVENTIONS.md`。
- `using` 引入的是**命名空间**（一整个），不像 Java `import` 通常精确到类。所以一行 `using System.Collections.Generic;` 就把 `List`、`Dictionary`、`HashSet` 全带进来。
- **文件级命名空间**（`namespace X;` 后面直接写代码，不用把整个文件缩进进大括号）是新语法，少一层缩进，本项目统一用它。

**为什么本仓的文件里几乎看不到 `using System...`**：两个工程都开了 `<ImplicitUsings>enable</ImplicitUsings>`（见 `rules/Tinderhearth.Rules.csproj`），编译器自动补上 `System`、`System.Collections.Generic`、`System.Linq` 这一批常用命名空间。所以 `CropDefinition` 里直接用 `IReadOnlyList<int>` 与 `.Sum()` 不需要写任何 `using`，文件头只留**本仓自己的**命名空间 —— 读文件头因此能一眼看出「它依赖本仓哪一层」。

---

## 二、属性（Property）

这是 Java 程序员最需要先适应的东西。**C# 不写 getter/setter 方法，而是用"属性"**。

```csharp
// rules/Progression/Roster.cs
public int Capacity { get; }                       // 只读属性（只有 get）

// rules/Economy/Plot.cs
public PlotState State { get; private set; }       // 外部只读，类内部可改
public bool WateredToday { get; private set; }
```

**对照 Java**：你在 Java 里会写

```java
private final int capacity;
public int getCapacity() { return capacity; }   // getter
// 可写的还要写 setter
```

C# 一行 `public int Capacity { get; }` 就等价于"私有字段 + getter"。**调用时也不写括号**：

```csharp
roster.Capacity        // C#：像访问字段一样，实际走属性
roster.getCapacity()   // Java 风格，C# 里没有
```

**本仓用到的几种形态**：

```csharp
// 1) 只读自动属性：只能在构造函数里赋值（相当于 Java 的 final 字段 + getter）
public int Capacity { get; }                                  // rules/Progression/Roster.cs

// 2) private set：外部只读、类内部可改（封装的关键）
public int WateredDaysThisCrop { get; private set; }           // rules/Economy/Plot.cs

// 3) 计算属性（get 里写逻辑，没有存储字段）——见下一节
public bool IsFull => _actorIds.Count >= Capacity;            // rules/Progression/Roster.cs

// 4) 初始化即赋值的只读属性：同时给出初值
public MotorState Motor { get; } = new();                      // rules/Combat/ActorCombatState.cs

// 5) init：只能在对象初始化时赋值，之后只读（见第十节）
public bool ManualAdvance { get; init; }                       // src/World/GameCamera.cs
```

**好处**：
- 封装成本极低——先写 `{ get; set; }`，将来要加校验/通知，改成 `{ get; private set; }` + 手写逻辑即可，**调用方代码不用改**（Java 里从字段改成 getter 是破坏性变更）。
- `{ get; private set; }` 做的是"外部只读、内部可控"。`Plot` 是这条的典型：外部读得到这一格现在是什么状态，但改它只能走 `Clear()`／`Till()`／`Plant()`／`Water()` 这些动作 —— 每个动作都先检查当前状态，不合法就返回 `false`。把 setter 开出去，"没锄过的地也能播种"就写得出来了。

---

## 三、表达式体成员 `=>`

当一个方法/属性的实现只有"返回一个表达式"时，可以用 `=>`（读作"goes to"）写成一行。**注意这里的 `=>` 不是 lambda，是方法体的简写**。

```csharp
// 计算属性（无存储字段，每次访问都算）
public bool IsFull => _actorIds.Count >= Capacity;                 // rules/Progression/Roster.cs
public bool Regrows => RegrowFromStage is not null;                // rules/Economy/CropDefinition.cs
public int DaysToFirstRipe => StageDays.Sum();

// 表达式体方法
// rules/Progression/Roster.cs
public bool Contains(string actorId) => _actorIds.Contains(actorId, StringComparer.Ordinal);

// rules/Combat/DepthOverlap.cs
public static double SeparationWorldPx(double aDepthWorldPx, double bDepthWorldPx) =>
    Math.Abs(aDepthWorldPx - bDepthWorldPx);
```

**对照 Java**：Java 没有这个。你得写

```java
public int getDaysToFirstRipe() { return stageDays.stream().mapToInt(Integer::intValue).sum(); }
```

**好处**：短小的取值/转发方法一行搞定，读起来像"定义即等式"。

**易混点**：`=>` 有两个含义，靠上下文区分：
- 成员定义处（`public bool IsFull => ...;`）＝方法体简写。
- 参数列表后（`t => t.Id == tabId`，见 `rules/Ui/Wristband.cs`）＝lambda 表达式（匿名函数），见第八节。

本项目的口径是「单行的取值、转发与简单计算用 `=>`，超过一行或有早返回就写完整方法体」，见代码仓 `CONVENTIONS.md` 的「表达式体成员」那一节。`Plot` 的那些动作方法全是完整方法体，正因为它们都有早返回。

---

## 四、可空引用类型 `?` 与 `!`

本项目开了 `<Nullable>enable</Nullable>`。它让编译器分析引用是否可能为空并给出警告；Java 通常依靠 `@Nullable`、静态分析工具或 `Optional`。这是一层编译期检查，不是绝对的运行时保证。

**在本仓它比"警告"更硬**：两个工程同时开了 `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`（见 `rules/Tinderhearth.Rules.csproj`），所以一条可空警告就是编译不过。

规则：**默认引用类型不可为 null**；要允许 null，得在类型后加 `?`。

```csharp
// rules/Economy/Plot.cs
// string? = 可能为 null；这一格没种东西时它就是 null
public string? CropId { get; private set; }

// rules/Economy/CropDefinition.cs
// int? = 可空的值类型。这里的 null **是一个合法取值**（表示一次性作物），不是"没填"
public required int? RegrowFromStage
{
    get;
    init => field = CheckRegrow(value);     // field 是 C# 14 的新关键字，见 §20
}

// rules/Economy/Plot.cs：空地调用方传 null，所以参数也是可空的
public void ApplySeasonChange(CropDefinition? crop, Season newSeason)
{
    if (State is not (PlotState.Planted or PlotState.Harvestable))
    {
        return;                         // 空地没有季节这回事，直接回
    }

    RequireCropForGrowth(crop);         // 有作物却没传定义 → 当场抛
    if (crop!.Seasons.Contains(newSeason))   // ← 这里的 ! 见下
    ...
```

**`!` 是"我确定不为 null"运算符（null-forgiving）**，压制编译器警告。上面那个 `crop!` 是本仓真实用到它的地方：`RequireCropForGrowth` 已经在 `crop` 为 null 时抛掉了，但编译器的流分析看不进那个方法，于是下一行仍认为 `crop` 可能为 null。

```csharp
// src/World/DepthVisual.cs：另一种更常见的处理法 —— 用模式匹配代替 !
if (GroundYWorldPx is not double ground)   // 可空 double 拆成非空局部变量
{
    return;                                // 拆不出来就不画
}
```

**能改结构就别用 `!`**：`is not double ground` 这种写法让编译器自己算出"后面这段里它一定非空"，而 `!` 是让编译器闭嘴。本仓只在"判空逻辑藏在另一个方法里"这一种情况下用 `!`。

**好处**：把"可能为 null"写进类型信息，编译器能提醒未处理的路径，大幅减少运行时空引用。`!`、反射、外部输入或不完整初始化仍能绕过检查，因此边界处仍要校验 —— 本仓的边界校验一律用 `ArgumentNullException.ThrowIfNull(...)` 这一批静态方法（见 §18）。

---

## 五、null 相关运算符

围绕 null 的几个语法糖，本仓前两个用得多：

### `?.` 空条件访问（safe navigation）

```csharp
// src/UI/InputRouter.cs：没人订阅这个事件时，整句什么都不做，不抛空引用
SkillGroupChanged?.Invoke(_modifiers.Active);
```

对照 Java：Java 没有同名的空条件访问运算符，通常写三元判空或用 `Optional.map(...)`。事件那一侧见第九节 —— `?.Invoke` 是本仓用 `?.` 最多的地方。

### `??` 空合并（null-coalescing）

```csharp
// src/World/DepthVisual.cs：射线探到地面就用那个 Y，没探到（悬崖外）就退到宿主节点的 Y
public DepthSubject Subject => new(Actor.DepthWorldPx, GroundYWorldPx ?? _host.GlobalPosition.Y);

// tests/Economy/PlotTests.cs：调用方没给就用这一份默认的测试用值
StageDays = stageDays ?? [1, 1, 1, 1],
```

`??` 还能接 `throw`，这在本仓比兜底默认值更常见 —— 因为「缺配置当场报错，不悄悄兜底」是硬约束：

```csharp
// rules/Ui/Wristband.cs：拼错标签页 id 不该静默变成「不可用」
var tab = Tabs.FirstOrDefault(t => t.Id == tabId)
    ?? throw new KeyNotFoundException($"手环没有这个标签页：{tabId}");

// rules/Foundation/Content/ContentJson.cs：一个内容文件解析成空是缺陷，不是空数据
return parsed ?? throw new InvalidDataException($"{whatForDiagnostics} 解析结果为空");
```

对照 Java：`Optional.ofNullable(x).map(...).orElseThrow(...)`。C# 的 `??` 右边可以直接是 `throw` 表达式，不用套 `Optional`。

### `??=` 空合并赋值（懒初始化）

```csharp
// 若 _cache 为 null，才创建并赋值（相当于懒加载）
_cache ??= CreateCache();
```

等价于 `if (_cache == null) _cache = ...;`。**本仓暂无**：会被反复查的表（`ContentJson.Options`、`TextCatalog.Empty`、`Wristband.Tabs`）都是静态只读成员、一次建好，没有"第一次用到才建"的场景。读到这个符号时知道它是懒初始化就够了。

---

## 六、switch 表达式

C# 的 `switch` **可以当表达式用**（直接返回值），比 Java 传统 switch 强太多。

```csharp
// rules/Combat/StatusEffects.cs：枚举 → 数组下标，写成一张表
private static int Index(StatusKind kind) => kind switch
{
    StatusKind.Hitstun => 0,
    StatusKind.Invulnerable => 1,
    _ => throw new ArgumentOutOfRangeException(nameof(kind), kind, "未知状态种类"),
};
```

注意最后那一臂：`_` 是 default，而本仓在这个位置放的是 `throw` 而不是一个兜底值。**枚举加了新取值却忘了在这里加一臂时，它当场响** —— 悄悄返回 0 会让新状态被当成硬直。

**对照 Java**：Java 14+ 有 `switch` 表达式（`case X -> ...`），比较接近了；但 C# 的更早、且能配**模式匹配**：

```csharp
// rules/Economy/CropDefinition.cs：null 模式、关系模式与 and 模式一起用
private static int? CheckRegrow(int? value) => value switch
{
    null => null,                            // null 模式：它是合法取值（一次性作物）
    >= 0 and < RipeStage => value,           // 关系 + and：落在合法区间内
    _ => throw new ArgumentOutOfRangeException(...),
};

// rules/Economy/Plot.cs：or 模式，把"允许的起步状态"写成一臂
State = initial switch
{
    PlotState.Uncleared or PlotState.Cleared or PlotState.Tilled => initial,
    _ => throw new ArgumentOutOfRangeException(...),
};

// rules/Economy/Plot.cs：is not + 括号里的 or 模式，读作"不是这两个状态之一"
if (State is not (PlotState.Planted or PlotState.Harvestable))
```

**好处**：
- "输入 → 输出"的映射（枚举转下标、合法区间判定）写得像一张表，清晰无遗漏。
- 编译器检查完整性——漏了分支会警告，而本仓警告即错误。
- `_`＝默认分支；`>= 0`＝关系模式；`A or B`＝或模式；`is`＝类型/常量模式。这些叫**模式匹配（pattern matching）**，Java 才刚开始有。

本项目另有一条相关纪律：**三元 `?:` 只许一层，嵌套三元要改写成 `switch`**，见代码仓 `CONVENTIONS.md` 的「三元与多路分派」那一节。

---

## 七、集合初始化 / 对象初始化器

**对象初始化器**：new 的时候直接用 `{ }` 给属性赋值，不用写一堆 setter 调用。

```csharp
// tests/Economy/PlotTests.cs：这些字段是 required 的，所以必须在初始化器里给齐（见 §18）
private static CropDefinition Crop(...) => new()
    {
        Id = "turnip",
        StageDays = stageDays ?? [1, 1, 1, 1],
        RegrowFromStage = regrowFromStage,
        Seasons = seasons ?? [Season.Spring],
        YieldItemId = "item_turnip",           // 逗号分隔的属性赋值
    };
```

**嵌套的集合初始化器**：属性本身是集合时，可以直接在 `{ }` 里塞元素，不必先 new 一个集合。

```csharp
// rules/Foundation/Content/ContentJson.cs
public static JsonSerializerOptions Options { get; } = new()
{
    PropertyNameCaseInsensitive = true,
    AllowTrailingCommas = true,
    ReadCommentHandling = JsonCommentHandling.Skip,
    Converters = { new JsonStringEnumConverter() },   // ← 嵌套：往已有的集合属性里加元素
};
```

**集合表达式 `[...]`（C# 12）**：本仓的集合初始化几乎全用这个形式，比 `new List<T>()` 短，而且不用重复写元素类型。

```csharp
private readonly List<string> _actorIds = [];              // rules/Progression/Roster.cs：空集合

// rules/Ui/Wristband.cs：静态表，顺序即显示顺序
public static readonly IReadOnlyList<WristbandTab> Tabs =
[
    new("notice", SurfaceKind.View),
    new("codex", SurfaceKind.View),
    ...
];

// rules/Foundation/Text/TextCatalog.cs：`..` 是展开（spread），把查询结果摊进新集合
public IReadOnlyList<string> MissingKeys(IEnumerable<string> requiredKeys) =>
    [.. requiredKeys.Where(k => !_entries.ContainsKey(k))];
```

**字典也能用索引器初始化**，键是元组时尤其好读：

```csharp
// rules/Ui/InputBindings.cs
new Dictionary<(string, InputDeviceKind), string>
{
    [(InputActions.Skills[0], InputDeviceKind.Gamepad)] = "手柄上由 LT + 面键组合解算发出",
    ...
};
```

**具名参数**（named argument）——调用时写出参数名，可读性高、还能跳过中间的可选参数。Java 完全没有，只能靠参数顺序或 Builder 模式。

```csharp
// tests/Economy/PlotTests.cs：三个数字连着排，不写名字读不出谁是谁
private static readonly HarvestYieldRule Yield = new(
    BaseCount: 10, MinWaterFactor: 0.5, MaxWaterFactor: 1.0);

// src/Platform/LocalPlayerController.cs：一串同类型的 bool，具名是唯一可读的写法
JumpPressed: router.IsJustPressed(InputActions.Jump),
LightPressed: router.IsJustPressed(InputActions.AttackLight),
```

`new()`（不写类型）叫**目标类型 new**：左边已声明类型时，右边不用重复写。`MotorState Motor { get; } = new();` 等价 `= new MotorState();`。本项目只在"类型可还原"处这么写（左边有显式类型，或方法有返回类型），口径见代码仓 `CONVENTIONS.md` 的「构造与 `new`」那一节。

---

## 八、LINQ（对应 Java Stream）

LINQ 是 C# 的集合查询，和 Java Stream 思路相近，但**不需要先 `.stream()`**：集合直接就能点出这些方法（它们是扩展方法）。需要落成具体集合时本仓用集合表达式 `[.. 查询]`，见下面那条差异。

```csharp
// 过滤（Java: .stream().filter(...)）
Tabs.Where(t => t.AvailableIn(context))                    // rules/Ui/Wristband.cs

// 找第一个匹配的，找不到返回 null/default（Java: findFirst().orElse(null)）
Tabs.FirstOrDefault(t => t.Id == tabId)                    // rules/Ui/Wristband.cs

// FirstOrDefault 还能显式给"找不到时返回什么"——这里用 -1 表示"没有不合法的项"
Enumerable.Range(0, value.Count).FirstOrDefault(i => value[i] < 1, -1)   // rules/Economy/CropDefinition.cs

// 投影/转换（Java: .map(...)）
catalog.Sources.Select(s => s.Name)                        // src/Main.cs

// 排序（Java: .sorted(...)）；字符串排序显式给比较器，见下面那条差异
files.Keys.Where(p => p.StartsWith(relativeDirectory + "/", StringComparison.Ordinal))
          .OrderBy(p => p, StringComparer.Ordinal)         // tests/Foundation/InMemoryContentSource.cs

// 求和、跳过前几项（Java: sum() / skip()）
StageDays.Sum()                                            // rules/Economy/CropDefinition.cs
StageDays.Skip(back).Sum()

// 去重计数：两个数不相等就说明有重复项（Java: distinct().count()）
InputActions.All.Distinct().Count()                        // tests/Ui/InputMappingTests.cs
```

**关键差异**：

- Java 常以 `.collect(Collectors.toList())` 收集结果；C# 对应用 `.ToList()`，但**本仓优先用集合表达式** `[.. 查询]`（见 §7），它少一次方法调用、也不用写元素类型。`.ToList()` 只在需要一个可继续改的 `List<T>` 时用（例如 `rules/Ui/SkillModifiers.cs` 里先 `ToList()` 再 `Clear()` 原字典）。
- `FirstOrDefault` / `SingleOrDefault`：找不到时返回该类型的默认值（引用类型是 null，int 是 0），不像 Java 返回 `Optional`。常配 `??` 兜底或 `?? throw`（见 §5）。
- `t => t.Id == tabId` 就是 **lambda**（匿名函数），跟 Java `s -> s.getId().equals(id)` 一样，只是箭头是 `=>`、比较用 `==`（字符串比较见下）。
- 本项目的口径是**优先 LINQ、不手写 `for`**，见代码仓 `CONVENTIONS.md` 的「集合与 LINQ」那一节；例外是逐帧路径与要早返回的循环。

⚠️ **字符串比较**：C# 里 `==` 对 `string` 是**比较内容**（值相等），不像 Java 的 `==` 比引用！所以 `t.Id == tabId` 是对的，不用 `.equals()`。（Java 程序员最容易在这里踩反——Java 要 `.equals()`，C# 直接 `==`。）

⚠️ **拿标识当键或做查找时要显式给比较器**：凡是键为**内容标识或角色标识**（跨 mod、跨存档要保持稳定的那种）的地方，本仓都传 `StringComparer.Ordinal`；`StartsWith`／`EndsWith` 一类传 `StringComparison.Ordinal`。

```csharp
// rules/Foundation/Actors/ActorControl.cs
private readonly Dictionary<string, IActorController> _byActorId = new(StringComparer.Ordinal);

// rules/Progression/Roster.cs
public bool Contains(string actorId) => _actorIds.Contains(actorId, StringComparer.Ordinal);
```

理由：默认比较在某些 API 上是**区域敏感**的，也就是说同一份数据在不同语言环境的机器上可能得出不同结果 —— 而内容标识（`turnip`、`item_turnip` 这种）是纯标识，按序数逐字节比才是它要的语义。这类差异不报错，只在别人的机器上表现为"某个角色加载不出来"。纯内部用的短命字典（例如 `rules/Ui/SkillModifiers.cs` 里"这个面键此刻驱动着哪个技能位"）没这层风险，就直接 `[]`。

---

## 九、委托与事件：`Action` / `event`

Java 里你会用接口（如 `OnClickListener`）做回调；C# 用**委托（delegate）**，`Action`/`Func` 是内置的通用委托类型。

`Action<T>` ＝ 接收 T、无返回值（相当于 Java `Consumer<T>`）；`Func<T, TResult>` ＝ 接收 T、返回 TResult（相当于 `Function<T,R>`）；无参无返回的 `Action` 相当于 `Runnable`。C# 统一只有这两个名字：`Action`（无返回）与 `Func`（有返回，最后一个泛型参数是返回类型）。

### `event`：观察者模式的语言级支持

本仓唯一的一对事件在输入门面上，通知 HUD 换按键提示：

```csharp
// src/UI/InputRouter.cs：声明（? 表示可空，即可能没人订阅）
public event Action<InputDeviceKind>? DeviceChanged;
public event Action<SkillGroup>? SkillGroupChanged;

// 同一个文件里触发（?. 保证没人订阅时不抛空引用）
if (before != _modifiers.Active)
{
    SkillGroupChanged?.Invoke(_modifiers.Active);
}
```

订阅（`+=`）与解绑（`-=`）成对出现：

```csharp
// src/UI/LevelHud.cs 的 _Ready：订阅事件而不是每帧轮询
_router.SkillGroupChanged += OnSkillGroupChanged;
_router.DeviceChanged += OnDeviceChanged;

// 同一个类的 _ExitTree：逐条解绑
_router.SkillGroupChanged -= OnSkillGroupChanged;
_router.DeviceChanged -= OnDeviceChanged;

// 处理器是具名方法，理由见下
private void OnSkillGroupChanged(SkillGroup group) => RefreshSkills();
```

**对照 Java**：Java 没有语言级 event，你得自己维护 `List<Listener>` + `addListener/removeListener` + 遍历调用。C# 的 `event` 把这套内建了：`+=` 加订阅、`-=` 退订、`?.Invoke(...)` 广播。

**两条纪律**（口径在代码仓 `CONVENTIONS.md` 的「事件订阅」那一节）：订阅必须在 `_ExitTree` 里解绑、与订阅成对；处理器用**具名方法**而不是 lambda，因为 lambda 要解绑就得保存并传回**同一个委托实例**，在 `-=` 时临时再写一个外观相同的新 lambda 是解不掉的 —— 而解不掉不报错，只表现为节点释放后回调还在跑。

**规则层现在一个 event 都没有**，这不是漏写：规则层的判定都是"调进去、拿返回值"的同步调用（`Plot.TryHarvest`、`DepthOverlap.WithHorizontal`），没有"过了一会儿有事发生"这种形状。将来统计事件总线那一批落地后规则层才会有"往外发"的一侧，用什么形状发到那时才定，进度见[待办台账](../spec/issues/README.md)。

---

## 十、enum / init / 元组

### enum（枚举）

跟 Java 类似，但 C# 枚举底层就是整数，更轻量：

```csharp
// rules/Economy/PlotState.cs（原文每个取值带一段 XML 注释，这里压成行尾注释）
public enum PlotState
{
    Uncleared,      // 未清理：上面有石头、树木或杂草
    Cleared,        // 可耕：清干净了，能盖房，不能播种
    Tilled,         // 已锄：能播种
    Planted,
    Harvestable,
    Withered,
}
```

对照 Java：Java 枚举是"功能完整的类"（能带方法/字段），C# 枚举默认只是命名整数（更接近 C 的 enum）。给枚举配数据时用**静态工具类 + switch 表达式**（`StatusEffects.Index`、`HudPalette.ColorOf`），而不是像 Java 那样在枚举里塞方法。

⚠️ **底层是整数，但本仓刻意不用那个序号做持久化**。`ContentJson.Options` 给 JSON 装了 `JsonStringEnumConverter`，枚举**按名字**读写：

```csharp
// rules/Foundation/Content/ContentJson.cs
Converters = { new JsonStringEnumConverter() },
```

理由写在那个文件里：序号在手写数据文件里读不出含义（`"seasons": [0, 1]` 要去查 0 是哪个季节），而且往枚举中间插一个取值会**静默改掉全部旧数据的含义**。按名字则是解析失败，而失败查得出来。遍历枚举全部取值用 `Enum.GetValues<HudGaugeKind>()`（本仓多处这么写），不靠"从 0 数到 N"。

### `init` 属性（不可变对象的优雅写法）

```csharp
// src/World/GameCamera.cs：只在 new 的时候设一次，之后只读
public bool ManualAdvance { get; init; }

// src/World/PlayerActor.cs：同一形状，测试与探针用它接管帧推进
public bool ManualPhysics { get; init; }
```

配合对象初始化器就是"造好即定型"：

```csharp
// src/World/TrainingRoom.cs：new 的时候设得上
_player = new PlayerActor { ManualPhysics = true, Position = new Vector2(PlayerX, GroundY) };
var spark = new HitSpark { Heavy = reaction.IsHeavy, ZIndex = SparkZ };
```

之后再写 `_player.ManualPhysics = false` 就编译不过。

对照 Java：类似 Java 的 `final` 字段，但 `init` 配合对象初始化器，比 Java 的"全参构造函数 / Builder"简洁得多——既保证不可变，又不用写一堆构造参数。`sealed`＝不可被继承（相当于 Java 的 `final class`），本仓的 record 一律 `sealed`。

### 元组（Tuple）：临时打包多个值，不必定义类

本仓最典型的用法是**拿元组当字典的复合键**：

```csharp
// rules/Ui/InputBindings.cs：键是"动作 + 设备族"两个东西合起来
public static readonly IReadOnlyDictionary<(string Action, InputDeviceKind Device), string> Exemptions =
    new Dictionary<(string, InputDeviceKind), string>
    {
        [(InputActions.Skills[0], InputDeviceKind.Gamepad)] = "手柄上由 LT + 面键组合解算发出",
        ...
    };

// tests/Ui/InputMappingTests.cs：查的时候也直接拿元组当键
var exempt = InputBindings.Exemptions.TryGetValue((action, device), out var why);
```

**遍历时解构**也常见：

```csharp
// rules/Foundation/Text/TextCatalog.cs：把 KeyValuePair 拆成两个变量
foreach (var (key, value) in table)
{
    merged[key] = value;
}
```

对照 Java：Java 没有原生元组（要么定义类，要么用 `Map.Entry`/第三方 `Pair`），更不能拿它当 `HashMap` 的键而自动获得按值的 hashCode。C# 的具名元组轻量、带名字、能解构，相等性按字段算 —— 所以它当键是安全的。

**边界**：元组适合"临时打包"。要被别处引用、要写文档注释、要带校验的数据一律用 `record`（见 §14）——本仓的 `ContentEntry`、`StatusEffect`、`HitReaction` 字段都不多，用的却是 record，因为它们各自要带一份说明"这个字段是什么量纲"。

---

## 十一、其他小语法

### `var`：局部变量类型推断

```csharp
// rules/Economy/Plot.cs：右边一眼看得出类型，所以用 var
var denominator = Math.Max(1, DaysThisCrop);
var raw = (double)WateredDaysThisCrop / denominator;
var factor = Math.Clamp(raw, rule.MinWaterFactor, rule.MaxWaterFactor);
```

跟 Java 10 的 `var` 一样，只能用于局部变量。本项目在右侧类型一眼可知时用 `var`，类型不显然时写全类型名，口径见代码仓 `CONVENTIONS.md` 的「局部变量与 `var`」那一节。字段、属性和参数一律写明确类型。

### 字符串插值 `$"..."`

本仓用它最多的地方是**错误信息**：把实际收到的值直接写进消息里，排错时不用再加一次日志。

```csharp
// rules/Economy/Plot.cs
throw new ArgumentException(
    $"这一格种的是 {CropId}，传进来的定义是 {crop.Id}", nameof(crop));

// rules/Economy/CropDefinition.cs：{} 里可以是表达式，不只是变量
$"要么落在 0 到 {RipeStage - 1} 之间（退回成熟那一阶段等于无限收获），实际 {value}"

// tests/Ui/HudTests.cs：带格式说明符
$"HUD 占屏 {share:P1}，超过一成就开始挤中间那块"     // :P1 = 百分比、1 位小数
```

对照 Java：Java 常用 `+`、`String.format(...)` 或 `"%s".formatted(...)`；文本块解决多行字面量，不等同于字符串插值。C# 的 `$"{x}"` 可直接嵌入表达式，`:P1` 这类是**格式说明符**。

### `const` 与 `static readonly`

```csharp
// rules/Combat/CombatFeel.cs：编译期常量（Java: static final 基本类型）
public const int PhysicsTicksPerSecond = 60;
public const int MoveSpeedPixelsPerSecond = 104;

// rules/Economy/CropDefinition.cs：const 之间可以互相推导
public const int StageCount = 5;
public const int RipeStage = StageCount - 1;

// rules/Ui/Wristband.cs：对象与集合用 static readonly（引用类型不能是 const）
public static readonly UiSurface Surface = new("wristband", UiLayer.Panel, SurfaceKind.View);
```

`const` 只能用于编译期能定死的值（数字/字符串）；对象/数组用 `static readonly`（相当于 Java `static final`）。注意 C# 的常量命名是 PascalCase 而不是 `UPPER_SNAKE`（见 §12），而**量纲写在名字里**是本仓的硬约定 —— `MoveSpeedPixelsPerSecond` 读得出它是"世界像素每秒"。

### `out` 参数：一个方法"返回"多个结果

```csharp
// rules/Economy/Plot.cs：返回 bool 说"收上来了没有"，件数从 out 带出
public bool TryHarvest(CropDefinition crop, HarvestYieldRule rule, out int count)

// tests/Economy/PlotTests.cs：调用侧就地声明变量
Assert.True(plot.TryHarvest(crop, Yield, out var count));
Assert.Equal(5, count);

// rules/Foundation/Actors/ActorControl.cs：字典的 TryGetValue 直接转发出去
public bool TryGet(string actorId, out IActorController? controller) =>
    _byActorId.TryGetValue(actorId, out controller);
```

`out` 表示"这个参数由方法内部赋值传出"。`TryXxx` 是 C# 的惯用法：返回 bool 表示成不成，`out` 参数带出值 —— 比 Java 的"先 containsKey 再 get"少一次查找。`out var count` 是就地声明变量。

**本仓为什么大量用它**：状态不对是玩家碰得到的正常结果（他对着没锄的地按了播种），不是缺陷，所以这类动作一律返回 `bool` 而不抛异常；真缺陷（调用方传错了作物定义）才抛。这条判据写在 `rules/Economy/Plot.cs` 的类注释里。

### 参数修饰符 `in`

```csharp
// rules/Combat/ActorCombatState.cs
public void Tick(in CombatInput input, bool onFloor)

// rules/Foundation/Actors/ActorControl.cs
ActorIntent Decide(in ActorView view);
```

`in` ＝ 按引用传、但方法内不许改。用在传递较大的 `readonly record struct` 时：避免逐帧拷贝，又不给"偷偷改调用方的输入"留口子。Java 没有对应物（对象天然按引用传，值类型只有基本类型）。

### 模式匹配 `is`

```csharp
// rules/Economy/CropDefinition.cs：可空 int 拆成非空局部变量 back
RegrowFromStage is int back ? StageDays.Skip(back).Sum() : null

// rules/Economy/CropDefinition.cs：属性模式，读作"非空且至少一项"
value is { Count: > 0 }

// src/World/TrainingRoom.cs：类型 + 属性模式 + not，一句话筛掉不关心的输入事件
if (@event is not InputEventKey { Pressed: true, Echo: false } key)
{
    return;
}
```

对照 Java 16+ 的 `if (obj instanceof String s)`（类型 + 绑定变量），C# 的 `is` 更早且更强（能匹配属性、区间、null）。最后那个例子里 `@event` 的 `@` 是**转义标识符**：`event` 是关键字，参数偏偏得叫这个名（Godot 虚方法的签名），前面加 `@` 就能当普通名字用。

---

## 十二、命名约定差异

C# 和 Java 命名习惯不同（本项目严格遵循 C# 官方，见 `CONVENTIONS.md`）：

| 元素 | Java 习惯 | C# 习惯（本项目） | 本仓的例子 |
| --- | --- | --- | --- |
| 类/接口 | PascalCase | PascalCase（一致） | `ContentCatalog` |
| **方法** | camelCase | **PascalCase** | `TryHarvest()` 而非 `tryHarvest()` |
| **属性/公有成员** | camelCase(getter) | **PascalCase** | `WateredToday` 而非 `isWateredToday()` |
| 局部变量/参数 | camelCase | camelCase（一致） | `int fallowRevertDays` |
| **私有字段** | camelCase | **`_camelCase`（下划线前缀）** | `_actorIds`、`_sources` |
| 常量 | UPPER_SNAKE | PascalCase | `PhysicsTicksPerSecond` 而非 `PHYSICS_TICKS` |
| 接口 | 无前缀 | **`I` 前缀** | `IActorController`、`IContentSource` |
| 大括号 | 行尾 `{` | **另起一行（Allman）** | 见下 |

大括号风格（本项目用 Allman，`{` 单独一行）：

```csharp
// rules/Progression/Roster.cs
public bool TryAdd(string actorId)
{                                    // ← { 另起一行
    ArgumentException.ThrowIfNullOrEmpty(actorId);
    if (IsFull || _actorIds.Contains(actorId, StringComparer.Ordinal))
    {                                // ← 单条语句的 if 也带大括号
        return false;
    }

    _actorIds.Add(actorId);
    return true;
}
```

Java 通常是 `public boolean tryAdd(...) {`（`{` 跟在行尾，K&R 风格）。**这只是风格差异，不影响功能**，但本项目统一 Allman（Godot 官方 C# 规范）。

**测试方法名是中文**，这是本仓刻意的：`public void 可耕格不能播种要先锄()`（见 `tests/Economy/PlotTests.cs`）。C# 标识符允许非 ASCII，而一条失败的测试名要能直接读成"哪条规则破了"。

---

## 十三、继承与多态

**先说本仓的实情，免得你照着继承层级去找**：规则层**一个 `abstract` 与 `virtual` 都没有**，也没有任何一个 `: base(...)`。复用靠的是接口加静态类，而不是基类往下传行为 —— 一层继承里"哪一半逻辑在父类"要跳着文件读，而判定要能脱引擎单测、越平越好。

所以本仓真实的多态只剩下面这些形状：

### `override`：重写引擎的虚方法（与 Java 最大的差异）

Java 方法**默认可重写**（除非 `final`）；**C# 默认不可重写，基类要显式加 `virtual`，子类重写要加 `override`**。引擎层的节点类全在重写 Godot 基类给好的 `virtual` 方法：

```csharp
// src/World/PlayerActor.cs
public partial class PlayerActor : CharacterBody2D, IBlockingActor, IHittable
{
    public override void _Ready() { ... }                    // 节点进树时
    public override void _PhysicsProcess(double delta) { ... }   // 每个物理帧
    public override void _Draw() { ... }                     // 需要重画时
}

// src/UI/LevelHud.cs：成对的两个，订阅与解绑各在一个里（见 §9）
public override void _Ready() { ... }
public override void _ExitTree() { ... }
```

**好处**：基类主动声明"可被重写"、子类主动声明"我在重写"，比 Java"默认全可重写"更防误改，编译器还校验签名匹配。Java 的 `@Override` 是可选注解；C# 的 `override` 是强制关键字 —— 把 `_Ready` 拼成 `_Redy` 在 Java 里只是多了个没人调的方法，在 C# 里是编译错误。

### 接口：本仓真正的扩展点

```csharp
// rules/Foundation/Actors/ActorControl.cs：本地玩家、AI、将来的远程玩家都实现它
public interface IActorController
{
    ActorControllerKind Kind { get; }

    ActorIntent Decide(in ActorView view);
}
```

一个类可以实现多个接口，`PlayerActor` 就同时是 `IBlockingActor` 与 `IHittable` —— 这与 Java 一样。本仓用它做两件事：把"谁驱动这个角色"变成可替换的（`ENG-5` 的预留），以及让编译器守住跨层约束（命中判定的两个参数都声明成 `IDepthActor`，于是"忘了给纵深"改签名才写得出来，见代码仓 `ARCHITECTURE.md`）。

**`sealed` 用得比 `virtual` 多**：本仓大量类型写成 `sealed class` / `sealed record`（相当于 Java 的 `final class`）。理由写在 `CONVENTIONS.md` 的「记录类型」那一节：它们不是设计为扩展点的类型，明说出来，读者就不会试着去继承。

### 另外三样语法本仓暂无，但要认得

- **`abstract class`**：与 Java 同义，不能直接 new、只能被继承。
- **`virtual`**：基类给方法加上它，子类才允许 `override`。上面那些 `_Ready`／`_Draw` 之所以能重写，正是因为 Godot 的基类给它们加了。
- **`: base(...)`**：子类构造函数调父类构造函数，写在**参数列表之后**（Java 是构造体内第一行 `super(...)`），位置不同、作用相同。

---

## 十四、struct 值类型 vs class 引用类型

Java 只有引用类型（基本类型 int/double 除外）。**C# 有 `class`（引用类型）和 `struct`（值类型）两种自定义类型**。本仓的值类型一律写成 `readonly record struct` —— `record` 负责相等性与 `ToString`，`readonly` 保证全字段只读，`struct` 让它按值传：

```csharp
// rules/Combat/StatusEffects.cs：一个状态的只读快照
public readonly record struct StatusEffect(StatusKind Kind, int RemainingFrames, bool Removable);

// rules/Combat/HitResolution.cs：一次命中该产生什么反应
public readonly record struct HitReaction(
    int KnockbackWorldPx, int HitstunFrames, int HitstopFrames, bool IsHeavy);

// rules/Foundation/Content/ContentCatalog.cs：一条内容文件，连同它来自哪个来源
public readonly record struct ContentEntry(string RelativePath, string SourceName, string Text);
```

括号里那一串叫**位置参数**（primary constructor）：编译器据此生成构造函数、只读属性、相等性比较与 `ToString`。Java 的 `record` 形状几乎一样，差别是 Java 的 record 仍是引用类型。

| | class 引用类型 | struct 值类型 |
| --- | --- | --- |
| 赋值/传参 | 传引用（改一个影响另一个） | **传拷贝**（改拷贝不影响原件） |
| 默认值 | `null` | 全字段零值（不会 null） |
| 相等 | 默认比引用（record class 比字段值） | 默认比字段值 |
| Java 对应 | 普通类 | Java 没有（最近似 `record` 但仍是引用类型） |

**判断口诀**：要共享／会变／有身份 → class（`Plot`、`Roster`、`ContentCatalog` 这类，它们都有自己的状态与动作）；轻量／不可变／是值 → struct（上面那批快照）。

**本仓有一处刻意反过来的，值得单独看**：`rules/Economy/HarvestYieldRule.cs` 是 `sealed record`（引用类型）而不是 `record struct`，理由写在它的注释里 —— 那一行是 `default` 一个 struct 会拿到全字段零值，**而零值正好绕过它的全部校验**。收几件那几个量还没有值，"缺配置要当场报错、不许悄悄兜底"是硬约束，于是不能允许任何人拿到一个合法但全 0 的实例。

上面那张表第二行就是这条的根据：**struct 有一个谁都造得出来的"零实例"，而它不过构造函数**。所以"这个类型的实例必须过校验"与"它是 struct"不能同时成立。

---

## 十五、运算符重载 + 重写 object 方法

**Java 不能重载运算符**；C# 可以：写一个 `public static bool operator ==(T a, T b)` 就能让 `a == b` 按你定的语义比较，`Equals`／`GetHashCode`／`ToString` 也能像 Java 的 `equals`／`hashCode`／`toString` 那样重写。规矩与 Java 一样：重写 `Equals` 就必须重写 `GetHashCode`，否则进 `HashSet`／`Dictionary` 会出错。

**本仓一个运算符重载都没有，一个手写的 `Equals` 也没有** —— 这不是还没做，而是不需要做：

- 要按值比较的类型全是 `record` 或 `record struct`，编译器**已经按字段生成**了 `Equals`、`GetHashCode`、`ToString` 与 `==`／`!=`。`tests/Combat/HitResolutionTests.cs` 里 `Assert.Equal(new HitReaction(...), light)` 能直接比出相等，靠的就是这套生成的相等性 —— 没有它，那条断言要逐字段写四遍。
- 需要复合键的地方用元组（见 §10），它的相等性同样是编译器给的。
- 需要非默认比较语义的地方（字符串按序数比）传 `StringComparer.Ordinal`，而不是去改类型的相等性（见 §8）。

所以这一节在本仓的用法是：**读到 `record` 就知道它已经有值相等性，不用去找 Equals 在哪**。哪天真要手写，判据是"语义确为值比较或值运算"（坐标、向量、金额），而不是"这样写起来短"。

---

## 十六、静态类 static class

纯判定、常量表与查表逻辑适合写成 `static class`。本仓拿它当这几种角色：

```csharp
// 一、纯判定：输入全从参数来，不持有任何状态、也不持有任何数
// rules/Combat/DepthOverlap.cs
public static class DepthOverlap
{
    public static bool Within(double aDepthWorldPx, double bDepthWorldPx, double toleranceWorldPx)
    ...
}

// 二、常量的唯一落点：调手感是改这一个文件，不是全代码翻魔法数
// rules/Combat/CombatFeel.cs
public static class CombatFeel
{
    public const int PhysicsTicksPerSecond = 60;
    ...
}

// 三、静态表 + 查询：表是数据，查询是一行 LINQ
// rules/Ui/Wristband.cs
public static class Wristband
{
    public static readonly IReadOnlyList<WristbandTab> Tabs = [ ... ];

    public static IEnumerable<WristbandTab> AvailableIn(UiContext context) =>
        Tabs.Where(t => t.AvailableIn(context));
}
```

`static class` = 不能 new、只能装静态成员的"函数与常量容器"，调用直接 `DepthOverlap.Within(...)`。对照 Java：Java 顶层类没有 `static` 修饰，你得写"全 static 方法 + 私有构造防实例化"的工具类（如 `Collections`）；C# 一个 `static class` 关键字表达此意图，编译器强制无实例成员、不可 new。

**这个形状与"有状态的 class"怎么分**：问"它记不记得上一次调用"。`Plot` 记得（这一格锄过没有），所以是 class；`DepthOverlap` 不记得，同样的输入永远同样的输出，所以是 static class —— 也因此它的测试不用搭任何环境。

---

## 十七、特性 Attribute + 泛型方法

### 特性（Attribute）≈ Java 注解

`[Xxx]` 对应 Java `@Xxx`，给代码贴元数据供框架读取。本仓现在只有测试框架那一批：

```csharp
// tests/Economy/PlotTests.cs
[Fact]                                   // ≈ JUnit @Test
public void 可耕格不能播种要先锄() { ... }

// tests/Economy/PlotTests.cs：一份用例跑多组数据
[Theory]                                 // ≈ JUnit @ParameterizedTest
[InlineData(0, 5)]                       // ≈ @CsvSource
[InlineData(3, 7)]
[InlineData(4, 10)]
public void 浇过的天数越多收得越多(int waterDays, int expected) { ... }
```

**Godot 的那两个特性本仓还没有**：`[Export]`（把字段暴露到检查器，值由作者在编辑器里填）与 `[GlobalClass]`（让编辑器把某个类型认成资源）。它们是分工的交界面 —— 代理定义 `[Export]` 项、作者填值，口径在设计仓 [ADR-0009](../decisions/ADR-0009-编辑器主导的开发模式.md)，落地进度见[待办台账](../spec/issues/README.md)。**规则层永远不会有它们**：`[Export]` 来自 GodotSharp，而规则层不引用 Godot，所以导出面只能长在引擎层的节点或 `Resource` 上，值再传进规则层。

### `partial`

```csharp
// src/World/PlayerActor.cs
public partial class PlayerActor : CharacterBody2D, IBlockingActor, IHittable { ... }
```

`partial` = 类定义可拆在多处、编译时合并。本项目 Godot 节点类都是 `partial`——因为 **Godot 的 C# 源生成器会自动生成另一半**（信号绑定等）和你这半合并。Java 没有（一个类必须写在一个文件里）。**规则层一个 `partial` 都没有**：那边没有源生成器参与。

### 泛型方法

```csharp
// rules/Foundation/Content/ContentJson.cs：全项目共用的一个解析入口
public static T Parse<T>(string json, string whatForDiagnostics)
{
    var parsed = JsonSerializer.Deserialize<T>(json, Options);
    return parsed ?? throw new InvalidDataException($"{whatForDiagnostics} 解析结果为空");
}

// 调用侧把 T 填成自己：rules/Economy/CropDefinition.cs
public static CropDefinition Parse(string json, string whatForDiagnostics) =>
    ContentJson.Parse<CropDefinition>(json, whatForDiagnostics);
```

同 Java `static <T> T parse(...)`，只是 `<T>` 位置不同。C# 泛型在运行时保留足够的类型信息，并允许 `List<int>` 直接使用值类型；Java 泛型采用类型擦除，基本类型需写成包装类 `List<Integer>`。

上面这一对还顺带示范了本仓的一条做法：**每个内容类型各自留一个 `Parse`，把泛型参数钉死在自己身上**。调用方因此写不出"拿作物的解析器去读角色文件"。

---

## 十八、另外几种会遇到的写法

除前文内容外，读代码时还会撞到下面这些。

### `required`：缺了就报错的属性

本仓的内容定义用它保证"数据文件缺一个键就当场炸"：

```csharp
// rules/Economy/CropDefinition.cs
public required IReadOnlyList<int> StageDays
{
    get;
    init => field = CheckStageDays(value);
}
```

`required` ＝ 构造这个对象时**必须**给这个属性赋值，否则编译不过；反序列化时缺这个键则由反序列化器抛错。

**为什么本仓要专门用它**：位置参数 `record` 配 `System.Text.Json` 时，JSON 里**缺字段不报错**，会拿 `default` 填（`GameConfig` 的注释记着那次实测，0 名册容量表现为"谁都招不进来"）。位置参数那一路的补法是在属性初始化器里校验（`GameConfig`、`HarvestYieldRule` 都这么做）。但 `CropDefinition.RegrowFromStage` 的 `null` **是合法值**，"缺键"与"显式写 null"用校验区分不出来 —— 这时只有 `required` 能把两者分开。

### `ArgumentNullException.ThrowIfNull` 这一批静态守卫

```csharp
ArgumentNullException.ThrowIfNull(crop);                    // rules/Economy/Plot.cs
ArgumentException.ThrowIfNullOrEmpty(actorId);              // rules/Progression/Roster.cs
ArgumentOutOfRangeException.ThrowIfNegativeOrZero(frames);  // rules/Combat/StatusEffects.cs
```

.NET 现成的参数校验入口，一行顶掉"if 判空再 throw"四行，而且异常消息里的参数名由编译器填（靠 `CallerArgumentExpression`，不用自己写 `nameof`）。Java 的近似物是 `Objects.requireNonNull`。

### 索引器：让自己的类型能用 `[]` 取值

```csharp
// rules/Foundation/Text/TextCatalog.cs
public string this[string key] =>
    _entries.TryGetValue(key, out var value) ? value : $"◆缺文本:{key}◆";
```

`this[...]` 定义的是"拿方括号访问这个对象"的行为，所以取文本写成 `text["boot.title"]`。缺键时刻意返回显眼占位而不是抛异常也不是空串：抛异常会让一句漏翻崩掉整个场景，空串会让漏翻悄悄消失。Java 只有数组和 `Map.get`，自定义类型做不到这个形式。

### `yield return`：惰性序列迭代器

```csharp
// src/Platform/GodotContentSource.cs：逐个产出路径，不先建一整个列表
foreach (var file in DirAccess.GetFilesAt(absolute))
{
    if (file.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
    {
        yield return $"{relativeDirectory}/{file}";
    }
}
```

`yield return` = 惰性生成序列（遍历到哪算到哪），`yield break` 提前终止。相当于 Java 手写 `Iterator` 或 Stream 惰性求值，被语法糖化。

### `using` 声明：作用域结束自动释放

```csharp
// src/Platform/GodotContentSource.cs
using var handle = FileAccess.Open(absolute, FileAccess.ModeFlags.Read);
if (handle is null)
{
    throw new FileNotFoundException(...);
}

return handle.GetAsText();     // 方法返回时 handle 自动关掉，不写 finally
```

注意它是 `using var x = ...;` 这种**声明形式**（C# 8），不是带大括号的 `using (...) { }` —— 作用域就是当前这个块。对照 Java 的 try-with-resources：Java 必须把资源括在 `try (...)` 里，所以多一层缩进。这个 `using` 与文件头的 `using` 是**两个不相干的东西**，同名而已。

### 本仓暂无、但读别处代码会遇到的

- **`async` / `await`**：异步等待。Godot 里常用在"等若干帧再做下一件事"。本仓暂无 —— 帧推进走 `_Process`／`_PhysicsProcess`，规则层是纯同步判定。
- **扩展方法**：给现有类型加调用形式，让 `Helper.Do(x, y)` 写成 `x.Do(y)`。本仓暂无自己写的，但天天在用别人的 —— 全部 LINQ 方法都是扩展方法。
- **局部函数**：在方法内部声明只供该流程使用的函数。本仓暂无，同类需求都做成了私有方法（`Plot.Grow`、`CropDefinition.CheckStageDays`），因为那样文档注释挂得上、堆栈里也有名字。

---

## 十九、C# 13 新增特性（.NET 9，2024 年 11 月）

### `params` 集合（不再只限数组）

C# 12 之前 `params` 只能修饰数组参数；C# 13 起可以修饰任意集合类型：

```csharp
// C# 13：params 可以是 List、Span、IEnumerable……
void Log(params ReadOnlySpan<string> messages) { ... }
void AddAll(params IEnumerable<int> values) { ... }
```

对 Java 程序员：Java 的可变参数 `String... args` 等价于 `params string[]`，C# 13 把这个能力推广到所有集合类型，同时避免了 `params array` 每次调用都分配堆数组的问题（`Span` 变体可走栈分配）。

**本仓暂无**：需要传一串东西的地方都直接收 `IReadOnlyList<T>` 或 `IEnumerable<T>`，调用侧用集合表达式 `[...]`（见 §7），比 `params` 更明确。

### `partial` 属性与索引器

C# 10 就有 `partial` 方法；C# 13 把 `partial` 扩展到属性和索引器，允许声明与实现分布在不同的 `partial` 文件里：

```csharp
// 声明半（通常由代码生成器输出）
public partial int Count { get; set; }

// 实现半（手写）
public partial int Count
{
    get => _items.Count;
    set => throw new NotSupportedException();
}
```

本项目 Godot 节点类都是 `partial`（源生成器需要），但**本仓暂无 `partial` 属性**：现在没有哪个生成器在这些类上输出属性声明。将来有了，实现就走这条路。

### `ref struct` 可实现接口

C# 12 及以前，`ref struct`（如 `Span<T>`）不能实现接口，因为接口装箱到堆会使 `ref struct` 的栈约束失效。C# 13 允许 `ref struct` 实现接口，但调用时要求泛型约束里有 `allows ref struct`，防止意外装箱：

```csharp
ref struct MyBuffer : IDisposable
{
    public void Dispose() { ... }
}

// 调用侧要声明 T allows ref struct 才能以接口方式使用
void Process<T>(T buffer) where T : IDisposable, allows ref struct { ... }
```

实用场景：高性能路径里需要统一接口但又不想堆分配时。本项目目前不涉及，但遇到 `allows ref struct` 约束时知道它的来源。

---

## 二十、C# 14 新增特性（.NET 10，2025 年 11 月）

### `field` 关键字——直接访问自动属性的后备字段

这是 C# 14 最实用的一条，**本仓已经在用**。以前自动属性 `{ get; set; }` 的后备字段是编译器生成的，代码里无法直接用；想加验证逻辑就必须把属性改成手写的完整形式。`field` 关键字解决了这个问题：

```csharp
// C# 14 之前：想加校验，必须自己声明一个后备字段
private IReadOnlyList<int> _stageDays;
public IReadOnlyList<int> StageDays
{
    get => _stageDays;
    init => _stageDays = CheckStageDays(value);
}

// C# 14：rules/Economy/CropDefinition.cs 里的真实写法，不需要那个 _stageDays
public required IReadOnlyList<int> StageDays
{
    get;
    init => field = CheckStageDays(value);
}
```

`field` 只在属性访问器的方法体内有效，指向该属性的编译器生成后备字段。对 Java 程序员：相当于在 setter 里直接写 `this.stageDays = ...` 而不用再声明一个 `private` 字段。

**它在本仓解决的是一个具体问题**：`CropDefinition` 的每个属性都要在赋值时校验（阶段天数的项数与下限、季节非空、标识非空），而它又必须用 `required`（理由见 §18）。没有 `field` 的话，这个类型要多出一批只为绕过语法而存在的私有字段，而每个字段都是一次可以写错的重复。

### 扩展成员（Extension Members）

C# 3 的扩展方法只能扩展方法；C# 14 把它推广到扩展属性、扩展运算符等，语法也改成了更清晰的块形式：

```csharp
// C# 14 新语法：扩展块，可以同时放多个扩展成员
extension(Record rec)
{
    // 扩展属性
    public bool IsActive => rec.Status == Status.Active;

    // 扩展方法（与旧语法 this 参数等价，但可以和扩展属性同块）
    public string DisplayName() => $"{rec.Name}（{rec.Role}）";
}
```

旧的 `static class` + `this` 参数写法仍然有效；新块语法更适合同时给一个类型加多个成员的场景。**本仓暂无**：还没有哪个类型需要从外部加成员 —— 自己的类型就写在自己的文件里。

### `nameof` 支持实例成员

C# 14 之前，`nameof` 用于实例成员时必须有实例或类型前缀（`nameof(rec.Name)` 或写成静态访问路径）；C# 14 允许在不能持有实例的上下文里对实例成员直接用 `nameof`。

**`nameof` 本身本仓到处在用**，它是错误消息不会过期的原因：

```csharp
// rules/Economy/CropDefinition.cs：消息里的字段名由编译器填，属性改名时它跟着改
throw new ArgumentOutOfRangeException(
    nameof(StageDays),
    $"作物定义的 {nameof(StageDays)} 第 {bad} 项必须至少 1 天，实际 {value[bad]}");
```

对 Java：相当于 Java 反射里的 `field.getName()` 但在编译期完成、重构时自动跟踪改名 —— 手写字符串 `"StageDays"` 会在改名后静默说错话，而 `nameof` 会编译不过。

---

## 附：读本项目代码的建议路径

按这个顺序读，每一步都能顺带认下一批语法：

1. `rules/Progression/Roster.cs` —— 最小的一个有状态类。属性、表达式体、`TryAdd` 的 bool 返回、`StringComparer.Ordinal`，一屏读完。
2. `rules/Economy/CropDefinition.cs` —— 内容定义长什么样。`sealed record`、`required`、`field`、`init` 校验、switch 表达式里的各种模式，本仓的语法密度最高处。
3. `rules/Economy/Plot.cs` —— 一台状态机。`private set`、`out` 参数、`is` 模式、"动作返回 bool、真缺陷才抛"那条判据。
4. `tests/Economy/PlotTests.cs` —— 上面那两个怎么被测。`[Fact]`／`[Theory]`、中文测试名、集合表达式与具名参数。
5. `rules/Combat/DepthOverlap.cs` —— 纯判定的静态类。顺带看它的注释怎么写"为什么这一半不在这里算"。
6. `src/UI/InputRouter.cs` 与 `src/UI/LevelHud.cs` —— 跨层那一侧。`event` 的声明、触发、订阅与解绑成对，四处分别在哪。

分层与边界的理由在代码仓 `ARCHITECTURE.md`，风格口径在 `CONVENTIONS.md`。遇到不认识的写法，先回本文查；查不到就往本文补一条（活文档）。
