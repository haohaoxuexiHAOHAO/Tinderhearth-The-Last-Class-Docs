#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数值模型的七天纸面推演（`GP-2`）。

为什么是脚本而不是手算表格：这六条数值前提彼此耦合 —— 改一个作物周期会动粮食曲线，
改一次委托报酬会动现金流，而正典写的是「必须先算出来才能判断第一周可玩性」。手算表格
改一个数就得全部重算，三周后也没人能验，那正是「结论必须有依据」要防的形状。
按 [WORKFLOW §5] 做成 `tools/` 下的入口。

**它不是游戏实现。** 参数在 design/numeric-model-params.json，公式在这里；游戏侧的落地
跟着各玩法实现需求分批走（`GP-2` PRD 非目标第 1 条）。等规则层实现了公式，两处会有漂移
风险，届时退役还是改成交叉验证，已记 `DOC-6`。

用法（从设计仓根目录运行）：
    python tools/simulate_week.py                 # 全部：属性派生、七天推演、前提判定
    python tools/simulate_week.py --curves        # 额外逐日打出四条曲线的明细表
    python tools/simulate_week.py --plan 均衡     # 只跑一份计划
    python tools/simulate_week.py --set economy.start_food=9
                                                  # 临时改一个参数重算，用来撞失败路径
    python tools/simulate_week.py --check-doc      # 只核文档与参数表：路径存在 + 路径旁的数字对得上
    python tools/simulate_week.py --check-doc --set attributes.level_cap=24
                                                  # 改参数不改文档，用来撞值校验的失败路径

输出约定（与 check_docs.py 一致）：固定 UTF-8；判定逐条打 [OK]／[FAIL]；末尾打覆盖量、
结果与一行 EXIT=。日志由本脚本自己写 UTF-8 到 logs/simulate_week-<时间戳>.log。

**参数缺失一律判失败，不用默认值静默补齐** —— 静默补齐会让「参数没写」伪装成「算过了」。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = ROOT / "design" / "numeric-model-params.json"
DESIGN_DOC = ROOT / "design" / "数值模型.md"
LOG_DIR = ROOT / "logs"
# 参数路径的写法：小写字母下划线开头，点分。只认这一种，认不出的由 check_doc 报出来。
PATH_RE = re.compile(r"[a-z_]+(?:\.[a-z_0-9]+)+")
# 设计文件正文里的裸数字。前后不许紧贴字母、下划线或点，否则会把参数路径里的段号也当成数。
BARE_NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")

_LINES: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    _LINES.append(text)


class ParamError(KeyError):
    pass


class Params:
    """按点分路径取参数。取不到就抛 —— 不给默认值。"""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.reads: set[str] = set()

    def __call__(self, path: str):
        self.reads.add(path)
        node = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise ParamError(f"参数表缺 {path}（缺在 {part} 这一段）")
            node = node[part]
        return node

    def override(self, path: str, raw: str) -> None:
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            if not isinstance(node, dict) or part not in node:
                raise ParamError(f"--set 的路径 {path} 不存在（缺在 {part}）")
            node = node[part]
        if parts[-1] not in node:
            raise ParamError(f"--set 的路径 {path} 不存在（缺在 {parts[-1]}）")
        old = node[parts[-1]]
        if not raw:
            raise ParamError(f"--set {path}= 没给值")
        try:
            node[parts[-1]] = json.loads(raw)
        except json.JSONDecodeError:
            node[parts[-1]] = raw       # 不是 JSON 就当字符串，例如 --set x=春
        say(f"[..]   覆盖参数 {path}：{old} → {node[parts[-1]]}")


# ── 判定 ──────────────────────────────────────────────────────────────
@dataclass
class Check:
    tag: str            # 六条前提用 P1..P6，PRD 附加约束用 C1..
    name: str
    ok: bool
    detail: str
    blame: str = ""     # 不成立时该改哪个参数


CHECKS: list[Check] = []

# 算出来的量。设计文件正文抄了其中一批（战力差、练满与还债天数……），而 --check-doc 只核
# 参数、核不了算出来的量 —— 所以在这里登记，跑完拿 DOC_CLAIMS 与正文比一遍（`DOC-12`）。
DERIVED: dict[str, float] = {}


def derive(key: str, value: float) -> float:
    DERIVED[key] = float(value)
    return value


def check(tag: str, name: str, ok: bool, detail: str, blame: str = "") -> None:
    CHECKS.append(Check(tag, name, ok, detail, blame))


def check_cross_plan(partial: bool, tag: str, name: str, ok: bool,
                     detail: str, blame: str, why_unjudgeable: str) -> None:
    """登记一条**跨计划聚合**的判定。

    这类判定（「至少两种安排成立」、「按最快的那份计划算还债天数」）只在跑了全部计划时
    才有意义；只跑一份时它们必然不成立，而那种失败与数值无关。报出来的后果很具体：
    读者会学会忽略 FAIL —— 那比没有判定更坏。所以局部范围里改成「未判」并写明原因。

    新增跨计划判定时走这个入口，别再各自打补丁 —— 本轮已经因此撞过两次（P1 与 C9）。
    """
    if partial:
        check(tag, f"{name}（局部范围未判）", True,
              f"{detail}。**这条没判**：{why_unjudgeable}", blame)
    else:
        check(tag, name, ok, detail, blame)


# ── 属性派生与战力 ────────────────────────────────────────────────────
@dataclass
class Sheet:
    label: str
    level: int
    str_: int
    agi: int
    vit: int
    int_: int
    hp: int = 0
    mp: int = 0
    sp: int = 0
    patk: float = 0.0
    matk: float = 0.0
    pdef: float = 0.0
    mdef: float = 0.0
    crit: float = 0.0
    atk_speed: float = 0.0
    p_mitigation: float = 0.0
    m_mitigation: float = 0.0
    effective_hp: float = 0.0

    def power(self, multiplier: float) -> float:
        """战力＝有效 HP × 输出。**走物理那一路**：普攻是物理的，C4 与 C6 也拿普攻当探针，
        三条判据用同一个基准才比得出意义。取大或加权会让战力差变成一个说不清由谁贡献的数。"""
        dps = self.patk * multiplier * self.atk_speed
        return self.effective_hp * dps


def build_sheet(p: Params, label: str, level: int, attrs: dict[str, int]) -> Sheet:
    s = Sheet(label, level, attrs["str"], attrs["agi"], attrs["vit"], attrs["int"])
    s.hp = round(p("derived.hp_base") + p("derived.hp_per_vit") * s.vit)
    s.mp = round(p("derived.mp_base") + p("derived.mp_per_int") * s.int_)
    s.sp = round(p("derived.sp_base") + p("derived.sp_per_vit") * s.vit)
    # 攻防分离：攻分物理（力量）与魔法（智力），防分两份且基底都由体质给。
    s.patk = p("derived.patk_base") + p("derived.patk_per_str") * s.str_
    s.matk = p("derived.matk_base") + p("derived.matk_per_int") * s.int_
    s.pdef = p("derived.pdef_base") + p("derived.pdef_per_vit") * s.vit
    s.mdef = p("derived.mdef_base") + p("derived.mdef_per_vit") * s.vit
    k = p("derived.def_softening_k")
    s.p_mitigation = s.pdef / (s.pdef + k)
    s.m_mitigation = s.mdef / (s.mdef + k)
    # 有效 HP 走物理那一路，与 power() 同一个基准。
    s.effective_hp = s.hp / (1.0 - s.p_mitigation)
    s.crit = min(p("derived.crit_cap"),
                 p("derived.crit_base") + p("derived.crit_per_agi") * s.agi)
    crit_mult = p("derived.crit_multiplier")
    s.atk_speed = (p("derived.atk_speed_base") + p("derived.atk_speed_per_agi") * s.agi) \
        * (1.0 + s.crit * (crit_mult - 1.0))
    return s


def spread_points(start: dict[str, int], points: int) -> dict[str, int]:
    """把属性点均分到四项。均分是最保守的假设：不假定玩家会堆单一属性。"""
    out = dict(start)
    keys = ["str", "agi", "vit", "int"]
    for i in range(points):
        out[keys[i % 4]] += 1
    return out


def analyse_attributes(p: Params) -> dict:
    cap = p("attributes.level_cap")
    per = p("attributes.attr_points_per_level")
    start = dict(p("attributes.start_protagonist"))
    maxed = spread_points(start, (cap - 1) * per)

    lv1 = build_sheet(p, "主角 1 级", 1, start)
    lvmax = build_sheet(p, f"主角 {cap} 级", cap, maxed)
    ml = p("move_multipliers.protagonist_light")
    gap = derive("战力差", lvmax.power(ml) / lv1.power(ml))
    lo, hi = p("meta.power_gap_target")
    check("C1", f"战力差落在 {lo}–{hi} 倍",
          lo <= gap <= hi,
          f"满级 ÷ 1 级 = {gap:.2f} 倍"
          f"（有效 HP {lv1.effective_hp:.0f}→{lvmax.effective_hp:.0f}，"
          f"物理攻击 {lv1.patk:.1f}→{lvmax.patk:.1f}）",
          "derived.hp_per_vit / derived.patk_per_str / attributes.level_cap")

    # 量级自检：HP 三位数、单次伤害两位数（对同级对手）。
    # **两路都量**：物理走 patk 对 pdef，魔法走 matk 对 mdef。魔法那一路借用同一个倍率当
    # 探针 —— 它只量量级，不代表某个真技能（真技能的倍率是技能字段，归 GP-31）。
    def hit(atk: float, mitigation: float, mult: float) -> float:
        return max(1.0, atk * mult * (1.0 - mitigation))

    student_start = dict(p("attributes.start_student"))
    st1 = build_sheet(p, "学生 1 级", 1, student_start)
    stmax = build_sheet(p, "满级学生", cap, spread_points(student_start, (cap - 1) * per))
    pdmg_lv1 = hit(lv1.patk, st1.p_mitigation, ml)
    pdmg_max = hit(lvmax.patk, stmax.p_mitigation, ml)
    mdmg_lv1 = hit(lv1.matk, st1.m_mitigation, ml)
    mdmg_max = hit(lvmax.matk, stmax.m_mitigation, ml)
    check("C6", "量级：HP 三位数、物理与魔法的代表性单次伤害都两位数",
          100 <= lv1.hp <= 999 and 100 <= lvmax.hp <= 999
          and all(10 <= d <= 99 for d in (pdmg_lv1, pdmg_max, mdmg_lv1, mdmg_max)),
          f"HP {lv1.hp}→{lvmax.hp}；物理 {pdmg_lv1:.1f}→{pdmg_max:.1f}；"
          f"魔法 {mdmg_lv1:.1f}→{mdmg_max:.1f}",
          "derived.hp_base / derived.patk_per_str / derived.matk_per_int / move_multipliers")

    # 主角伤害必须显著低于学生（人物正典：主角低伤辅助，伤害来自学生）。
    #
    # **量测点在状态上，不在倍率上。** 倍率表里主角与学生同名招式同值，削弱全部由
    # 「薪尽火传」那条永久状态承担。量倍率之比会漏掉状态那一层 —— 而漏掉的那一层正是
    # 全部削弱，于是判据会一直报通过、实际比值却是另一个数。
    #
    # 这条判两件事，因为「削弱只有一个来源」要这两件同时成立：
    #   ① 同名招式两边同值 —— 不然倍率与状态各削一次，就是削两次；
    #   ② 状态在场时的实际输出比 ≤ 0.5 —— 削得够，教练定位才不只存在于文档里。
    # 只判 ② 挡不住 ①：再压低主角的倍率只会让比值更小，② 照样通过。
    sl = p("move_multipliers.student_light")
    sh = p("move_multipliers.student_heavy")
    same_mult = ml == sl and p("move_multipliers.protagonist_heavy") == sh
    self_f = p("flame_passed_on.protagonist_output_factor")
    ally_f = p("flame_passed_on.student_output_factor")

    def output(sheet: Sheet, mult: float, factor: float) -> float:
        """「薪尽火传」在场时的实际输出。普攻当探针，与 C1、C6 同一个基准。"""
        return sheet.patk * mult * sheet.atk_speed * factor

    # 两端各判一次：主角起步四项都比学生高一点，所以两端的比值不一样，只量一端会漏掉另一端。
    pro_lv1, stu_lv1 = output(lv1, ml, self_f), output(st1, sl, ally_f)
    pro_max, stu_max = output(lvmax, ml, self_f), output(stmax, sl, ally_f)
    ratio_lv1 = derive("薪尽火传下输出比1级", pro_lv1 / stu_lv1)
    ratio_max = derive("薪尽火传下输出比满级", pro_max / stu_max)
    check("C4", "「薪尽火传」在场时主角实际输出显著低于学生（比值 ≤ 0.5，两端各判）",
          same_mult and ratio_lv1 <= 0.5 and ratio_max <= 0.5,
          f"倍率两边{'同值' if same_mult else '**不同值，削弱有两个来源**'}"
          f"（轻 {ml}／{sl}，重 {p('move_multipliers.protagonist_heavy')}／{sh}）；"
          f"状态 ×{self_f} 对 ×{ally_f}；"
          f"1 级 {pro_lv1:.1f} ÷ {stu_lv1:.1f} = {ratio_lv1:.2f}，"
          f"满级 {pro_max:.1f} ÷ {stu_max:.1f} = {ratio_max:.2f}",
          "flame_passed_on.protagonist_output_factor / "
          "flame_passed_on.student_output_factor / move_multipliers")

    # 天赋点总量必须显著少于节点数。
    nodes = p("growth.talent_nodes_total")
    pts = p("growth.talent_points_cap")
    from_lv = p("growth.talent_points_from_levels")
    from_tr = p("growth.talent_points_from_training")
    check("C2", "天赋点总量显著少于节点数（比例 ≤ 0.6）",
          pts / nodes <= 0.6 and from_lv + from_tr == pts and from_tr > from_lv,
          f"{pts} ÷ {nodes} = {pts / nodes:.2f}；来源 升级 {from_lv} + 训练 {from_tr}"
          f"（训练是主要来源）",
          "growth.talent_points_cap / growth.talent_points_from_training")

    # 精准防御回蓝效率不得高于进攻回蓝（战斗与关卡正典的硬约束）。
    atk_mp = derive("进攻回蓝MP每秒",
                    p("resources.mp_per_light_hit") * p("resources.light_hits_per_second"))
    guard_mp = derive("精准防御回蓝MP每秒",
                      p("resources.perfect_guard_mp")
                      * p("resources.perfect_guard_opportunities_per_second"))
    check("C3", "精准防御回蓝效率不高于进攻回蓝",
          guard_mp <= atk_mp,
          f"进攻 {atk_mp:.2f} MP/s，精准防御 {guard_mp:.2f} MP/s",
          "resources.perfect_guard_mp / resources.perfect_guard_opportunities_per_second")

    # 训练经验必须明显低于出征。
    sortie_exp = p("growth.exp_per_sortie_low")
    train_exp = p("growth.exp_per_training_day")
    check("C5", "训练经验明显低于出征（≤ 1/3）",
          train_exp <= sortie_exp / 3,
          f"训练 {train_exp}／出征 {sortie_exp} = {train_exp / sortie_exp:.2f}",
          "growth.exp_per_training_day")

    base = p("growth.exp_curve_base")
    expo = p("growth.exp_curve_exponent")
    total_exp = sum(base * (lv ** expo) for lv in range(1, cap))
    sorties_to_cap = total_exp / sortie_exp
    return {"lv1": lv1, "lvmax": lvmax, "gap": gap, "student": st1,
            "total_exp": total_exp, "sorties_to_cap": sorties_to_cap}


# ── 七天推演 ──────────────────────────────────────────────────────────
@dataclass
class DayRow:
    day: int
    hours_used: float
    hours_limit: float
    vigor_used: int
    vigor_limit: int
    copper: int
    food: int
    note: str = ""


@dataclass
class SimResult:
    plan: str
    rows: list[DayRow] = field(default_factory=list)
    first_harvest_day: int | None = None
    food_before_first_harvest: int = 0
    overtime_days: list[int] = field(default_factory=list)
    overvigor_days: list[int] = field(default_factory=list)
    negative_cash_days: list[int] = field(default_factory=list)
    negative_food_days: list[int] = field(default_factory=list)
    student_overvigor: list[str] = field(default_factory=list)


def vigor_limit(p: Params, vit: int) -> int:
    """经营侧的当日预算上限（精力条）。与战斗侧的体力条是两条不共用的资源。

    住宿等级从参数表读，不写死在代码里 —— 它是推演的一条假设，藏在函数默认值里
    就看不见了，而看不见的假设正是「参数缺失不许静默补齐」要防的东西。"""
    level = p("week_plan.housing_level_at_start")
    return round(p("vigor.base") + p("vigor.per_vit") * vit
                 + p("vigor.housing_by_level")[level - 1]
                 + p("vigor.meal_full") + p("vigor.health_normal"))


def simulate(p: Params, plan_name: str) -> SimResult:
    plan = p(f"week_plan.plans.{plan_name}")
    res = SimResult(plan_name)

    copper = p("economy.start_copper")
    food = p("economy.start_food")
    students = p("week_plan.students_at_start")
    people = students + 1
    food_per_day = p("economy.food_per_person_per_day") * people

    hero = dict(p("attributes.start_protagonist"))
    hero_limit = vigor_limit(p, hero["vit"])
    stu = dict(p("attributes.start_student"))
    stu_limit = vigor_limit(p, stu["vit"])

    crops = p("farm.crops")
    growing: list[dict] = []      # {"crop":名, "cells":n, "ready_day":d}
    hours_limit = p("time.playable_hours")

    for entry in plan:
        day = entry["day"]
        note: list[str] = []

        # 播种：先付种子钱
        for crop, cells in entry.get("sow", {}).items():
            if crop not in crops:
                raise ParamError(f"计划里播种了参数表没有的作物 {crop}")
            cost = crops[crop]["seed_copper"] * cells
            copper -= cost
            growing.append({"crop": crop, "cells": cells,
                            "ready_day": day + crops[crop]["grow_days"]})
            note.append(f"播 {crop}×{cells}（−{cost} 铜）")

        # 主角行动
        hours = 0.0
        vigor = 0
        for act in entry["protagonist"]:
            a = p(f"actions.{act}")
            hours += a["hours"]
            vigor += a["vigor"]
            if act.startswith("sortie_"):
                kind = act.split("_", 1)[1]
                reward = p(f"economy.mission_reward_copper.{kind}")
                loot = p(f"economy.mission_loot_expected_copper.{kind}")
                cost = p("economy.consumable_expected_copper_per_sortie")
                injury = p("economy.injury_probability_low_mission") \
                    * p("economy.treatment_fast_copper")
                net = reward + loot - cost - injury
                copper += net
                note.append(f"{kind} 净 +{net:.0f} 铜")

        if hours > hours_limit:
            res.overtime_days.append(day)
        if vigor > hero_limit:
            res.overvigor_days.append(day)

        # 学生派工
        for who, job in entry["assignments"].items():
            need = p(f"assignments.{job}.vigor")
            if need > stu_limit:
                res.student_overvigor.append(f"第 {day} 天 {who} 做 {job}")

        # 收获（成熟即收，不靠计划里的标记）
        harvested = [g for g in growing if g["ready_day"] <= day]
        if harvested and res.first_harvest_day is None:
            res.first_harvest_day = day
            # 收获送达那一刻手里还剩多少 —— 这才是「缓冲」的量。当天的饭还没吃，
            # 所以不能先扣一天：先扣会把缓冲少算整整一天。
            res.food_before_first_harvest = food
        for g in harvested:
            info = crops[g["crop"]]
            amount = info["yield_per_cell"] * g["cells"]
            if info["food"]:
                food += amount
                note.append(f"收 {g['crop']} {amount} 份")
            else:
                gain = amount * info["sell_copper"]
                copper += gain
                note.append(f"收 {g['crop']} {amount} 份卖 +{gain} 铜")
            growing.remove(g)

        # 吃饭
        food -= food_per_day
        if food < 0:
            res.negative_food_days.append(day)
        if copper < 0:
            res.negative_cash_days.append(day)

        res.rows.append(DayRow(day, hours, hours_limit, vigor, hero_limit,
                               round(copper), food, "；".join(note)))
    return res


# ── 六条数值前提 ──────────────────────────────────────────────────────
def check_premises(p: Params, sims: dict[str, SimResult], sheets: dict) -> None:
    # P1：19 游戏小时装得下，且至少两种成立的一日安排。
    # 「至少两种」这半条只有在跑了全部计划时才判得了；只跑一份时它必然不成立，
    # 那种失败与数值无关，报出来只会训练人忽略 FAIL。所以局部范围里改判「跑过的都成立」，
    # 并在判定文字里写明这一轮没覆盖哪半条。
    feasible = [name for name, r in sims.items()
                if not r.overtime_days and not r.overvigor_days
                and not r.student_overvigor]
    broken = {n: {"超时": r.overtime_days, "超精力": r.overvigor_days,
                  "学生超精力": r.student_overvigor}
              for n, r in sims.items() if n not in feasible}
    total_plans = len(p("week_plan.plans"))
    partial = len(sims) < total_plans
    # 跑过的计划本身超时超精力，是真失败，局部范围也照判。
    check("P1a", "跑过的每份安排都装得进 19 小时与精力上限",
          not broken,
          f"跑了 {list(sims)}；成立 {feasible}；不成立 {broken}",
          "actions 一节的 hours 与 vigor / vigor.per_vit")
    check_cross_plan(partial, "P1b", "至少两种一日安排成立",
                     len(feasible) >= 2,
                     f"成立的安排 {feasible}（参数表共 {total_plans} 份计划）",
                     "week_plan.plans",
                     f"只跑了 {len(sims)}/{total_plans} 份，不带 --plan 才判得了")

    # P2：至少一种作物生长周期 ≤ 4 天
    crops = p("farm.crops")
    fast = {n: c["grow_days"] for n, c in crops.items() if c["grow_days"] <= 4}
    check("P2", "至少一种作物生长周期 ≤ 4 天",
          bool(fast),
          f"符合的 {fast}；全部周期 { {n: c['grow_days'] for n, c in crops.items()} }",
          "farm.crops.*.grow_days")

    # P3：起始资金／粮食／债务本金三者比例 —— 撑到第一次收获且不断粮。
    # 按第一份计划判；判定文字里写明是哪一份，免得读者以为它覆盖了全部计划。
    ref = sims[next(iter(sims))]
    people = p("week_plan.students_at_start") + 1
    per_day = p("economy.food_per_person_per_day") * people
    buffer_days = derive("收获时缓冲天数",
                         ref.food_before_first_harvest / per_day if per_day else 0)
    if ref.first_harvest_day is not None:
        derive("第一次收获天", ref.first_harvest_day)
    ok3 = (not ref.negative_food_days and not ref.negative_cash_days
           and 1.0 <= buffer_days <= 2.0 and ref.first_harvest_day is not None)
    check("P3", "撑到第一次收获且不断粮，收获时仍余 1–2 天缓冲",
          ok3,
          f"按计划「{ref.plan}」：第一次收获在第 {ref.first_harvest_day} 天，收获前余 "
          f"{ref.food_before_first_harvest} 份 = {buffer_days:.2f} 天；"
          f"断粮日 {ref.negative_food_days}，现金为负日 {ref.negative_cash_days}",
          "economy.start_food / economy.start_copper / farm.crops.*.grow_days")

    # P4：一次低难度委托的报酬 ÷ 时间与精力消耗
    lines = []
    ok4 = True
    for kind in ("gather", "clear", "escort"):
        a = p(f"actions.sortie_{kind}")
        reward = p(f"economy.mission_reward_copper.{kind}")
        loot = p(f"economy.mission_loot_expected_copper.{kind}")
        net = reward + loot - p("economy.consumable_expected_copper_per_sortie") \
            - p("economy.injury_probability_low_mission") * p("economy.treatment_fast_copper")
        day_food = p("economy.food_per_person_per_day") \
            * (p("week_plan.students_at_start") + 1) * p("economy.food_buy_copper")
        good = net > 0 and net >= day_food
        ok4 = ok4 and good
        lines.append(f"{kind} 净 {net:.0f} 铜／{a['hours']}h／{a['vigor']}EN "
                     f"= {net / a['hours']:.1f} 铜每小时、{net / a['vigor']:.2f} 铜每点精力"
                     f"（全队一天粮食成本 {day_food} 铜）{'' if good else ' ← 不足'}")
    check("P4", "低难度委托净收益为正，且不低于全队一天的粮食成本",
          ok4, "；".join(lines),
          "economy.mission_reward_copper / economy.mission_loot_expected_copper")

    # P5：治疗费用 ÷ 委托报酬
    treat = p("economy.treatment_fast_copper")
    low_reward = p("economy.mission_reward_copper.gather")
    ratio = treat / low_reward
    slow, fast_d = p("economy.treatment_slow_days"), p("economy.treatment_fast_days")
    check("P5", "花钱快治是真选项（治疗费 ≤ 低难度报酬的 2 倍，且省下的天数 ≥ 2）",
          ratio <= 2.0 and (slow - fast_d) >= 2,
          f"治疗费 {treat} ÷ 采集报酬 {low_reward} = {ratio:.2f} 倍；"
          f"慢养 {slow} 天 vs 快治 {fast_d} 天，省 {slow - fast_d} 天",
          "economy.treatment_fast_copper / economy.treatment_slow_days")

    # P6：偏好溢价与批量递减，须让每季重新决定种什么
    pref = p("pricing.demand_preferred")
    thr = p("pricing.supply_batch_threshold")
    decay = p("pricing.supply_step_decay")
    floor = p("pricing.supply_floor")
    cells = p("farm.starting_plot_cells")

    def season_income(crop_name: str, preferred: bool) -> float:
        c = crops[crop_name]
        cycles = p("time.season_days") // c["grow_days"]
        total = 0.0
        for _ in range(cycles):
            units = c["yield_per_cell"] * cells
            demand = pref if preferred else 1.0
            revenue = 0.0
            sold = 0
            while sold < units:
                batch = min(thr, units - sold)
                steps = sold // thr
                supply = max(floor, 1.0 - decay * steps)
                revenue += batch * c["sell_copper"] * demand * supply
                sold += batch
            total += revenue - c["seed_copper"] * cells
        return total

    best_base = max(crops, key=lambda n: crops[n]["sell_copper"])
    others = [n for n in crops if n != best_base]
    pref_pick = max(others, key=lambda n: season_income(n, True))
    income_pref = season_income(pref_pick, True)
    income_base = season_income(best_base, False)
    check("P6", "偏好溢价足以让「按偏好种」优于「按最高基础价种」",
          income_pref > income_base,
          f"按偏好种 {pref_pick} 一季 {income_pref:.0f} 铜 > "
          f"按最高基础价种 {best_base} 一季 {income_base:.0f} 铜"
          f"（溢价 {pref}，批量阈值 {thr}，每档递减 {decay}）",
          "pricing.demand_preferred / pricing.supply_step_decay")

    # 附加：第二季利息不得压过前期收入
    principal = p("economy.debt_principal_copper")
    rate = p("economy.debt_quarterly_rate")
    interest = principal * rate
    per_day_interest = derive("每天利息铜", interest / p("time.season_days"))
    check("C8", "第二季利息折到每天不超过一条低难度委托报酬的一半",
          per_day_interest <= low_reward * 0.5,
          f"本金 {principal} 铜 × {rate} = 一季 {interest:.0f} 铜 = 每天 "
          f"{per_day_interest:.1f} 铜；采集报酬 {low_reward} 铜",
          "economy.debt_principal_copper / economy.debt_quarterly_rate")

    # 附加：两条长期目标（练满与还清债务）必须落在同一量级，否则先到的那条会让另一条失去意义
    best = max(sims.values(), key=lambda r: r.rows[-1].copper)
    days = len(best.rows)
    net_per_day = (best.rows[-1].copper - p("economy.start_copper")) / days
    days_to_repay = derive("还债天数",
                           principal / net_per_day if net_per_day > 0 else float("inf"))
    sorties = sheets["sorties_to_cap"]
    sorties_per_day = 1.5
    days_to_cap = derive("练满天数", sorties / sorties_per_day)
    ratio_goals = derive("两条目标天数比",
                         days_to_cap / days_to_repay if days_to_repay else float("inf"))
    check_cross_plan(
        partial, "C9", "练满与还清债务落在同一量级（天数比 0.5–2 倍）",
        0.5 <= ratio_goals <= 2.0,
        f"满级需 {sheets['total_exp']:.0f} 经验 = {sorties:.0f} 次低难度出征 ≈ "
        f"{days_to_cap:.0f} 天（按每天 {sorties_per_day} 次）；还债需 {days_to_repay:.0f} 天"
        f"（按「{best.plan}」的日净收入 {net_per_day:.1f} 铜）；比 {ratio_goals:.2f}",
        "growth.exp_curve_base / growth.exp_curve_exponent / economy.debt_principal_copper",
        "还债天数按收入最高的那份计划算，只跑一份时这个基准是任意的")

    # 附加：容量必须造成一次取舍，但不频繁被迫丢弃
    kinds = p("capacity.expected_sortie_item_kinds")
    slots = p("capacity.backpack_slots_by_level")[0]
    derive("背包占用百分比", kinds / slots * 100)
    check("C7", "一次出征的产出种类接近但不超过初级背包格数（造成取舍而非频繁丢弃）",
          slots * 0.7 <= kinds <= slots,
          f"一次出征约 {kinds} 种物品，初级背包 {slots} 格，占用 {kinds / slots:.0%}",
          "capacity.backpack_slots_by_level / capacity.expected_sortie_item_kinds")


# ── 正文抄的「算出来的量」 ────────────────────────────────────────────
# 设计文件写着「不写当前实测值」，但有几处为了把话说清还是抄了算出来的量（摘要靠战力差那个
# 倍数支撑「只解释一半胜负」，C9 靠两个天数说明同量级）。删掉它们会让那几句变模糊，所以留，
# 但**每一处都要在这里登记**，跑完与正文比一遍。`DOC-12`。
#
# 每条是（说的是哪一处, 从正文抓数字的正则, DERIVED 里的键, 小数位）。
# **抓不到也算失败** —— 不然把句子改个说法就能静默关掉一条判定，那比没有判定更坏。
DOC_CLAIMS: tuple[tuple[str, str, str, int], ...] = (
    ("摘要的战力差",          r"同一角色的战力只涨 ([\d.]+) 倍",        "战力差",            2),
    ("成长一节的战力差",      r"15/15/14/14，战力差 ([\d.]+) 倍",       "战力差",            2),
    ("C9 的练满天数",         r"当前参数下练满约 (\d+) 天",             "练满天数",          0),
    ("C9 的还债天数",         r"练满约 \d+ 天、还债约 (\d+) 天",        "还债天数",          0),
    ("C9 的两条目标天数比",   r"还债约 \d+ 天，比 ([\d.]+)",            "两条目标天数比",    2),
    ("经济一节的还债天数",    r"约 (\d+) 天净收入",                     "还债天数",          0),
    ("经济一节的每天利息",    r"利率只做到每天 (\d+) 铜",               "每天利息铜",        0),
    ("C4 的 1 级实测比",      r"当前实测：1 级 ([\d.]+) 倍",            "薪尽火传下输出比1级",   2),
    ("C4 的满级实测比",       r"当前实测：1 级 [\d.]+ 倍，满级 ([\d.]+) 倍",
                                                                        "薪尽火传下输出比满级",  2),
    ("进攻回蓝效率",          r"当前是 ([\d.]+) MP/s",                  "进攻回蓝MP每秒",    2),
    ("精准防御回蓝效率",      r"MP/s 对 ([\d.]+) MP/s",                 "精准防御回蓝MP每秒", 2),
    ("第一次收获在第几天",    r"第一次收获在第 (\d+) 天",               "第一次收获天",      0),
    ("收获时的缓冲天数",      r"= ([\d.]+) 天缓冲",                     "收获时缓冲天数",    2),
    ("一次出征占背包的比例",  r"占初级背包 \d+ 格的 (\d+)%",            "背包占用百分比",    0),
)


def check_doc_claims(partial: bool) -> int:
    """把正文抄的算出来的量与本轮真算出来的比一遍。

    比的办法是用脚本自己的格式化再格一次，所以「0.6 与 0.60」「10 与 10.0」不会误报 ——
    判的是同一个数，不是同一串字符。
    """
    if not DESIGN_DOC.is_file():
        say(f"[FAIL] 找不到设计文件 {DESIGN_DOC.relative_to(ROOT)}")
        return 1
    if partial:
        say("[..]   正文抄的算出来的量：**本轮未判** —— 带了 --plan，"
            "还债与缓冲天数的基准是任意的，判了只会训练人忽略 FAIL")
        return 0

    text = DESIGN_DOC.read_text(encoding="utf-8")
    bad: list[str] = []
    for label, pattern, key, digits in DOC_CLAIMS:
        found = re.findall(pattern, text)
        if len(found) != 1:
            bad.append(f"{label}：正文里匹配到 {len(found)} 处（应当恰好 1 处）"
                       f"—— 句子被改写过就要同时改这里的正则：{pattern}")
            continue
        if key not in DERIVED:
            bad.append(f"{label}：本轮没算出 `{key}`，登记表与算式对不上")
            continue
        want = f"{DERIVED[key]:.{digits}f}"
        got = f"{float(found[0]):.{digits}f}"
        if want != got:
            bad.append(f"{label}：正文写 {found[0]}，算出来是 {want}")

    say(f"正文覆盖量：核了 {len(DOC_CLAIMS)} 处正文抄的算出来的量")
    if bad:
        for line in bad:
            say(f"[FAIL] {line}")
        return 1
    say("[OK] 正文抄的算出来的量与本轮算的一致")
    return 0


# ── 输出 ──────────────────────────────────────────────────────────────
def check_doc(p: Params) -> int:
    """核对设计文件与参数表没有分叉：路径存在，且写在路径旁边的数字与参数表一致。

    为什么需要它：设计文件解释公式、参数表持有值，两处必然一起改。人工核对是那种没人会真
    做第二次的事，所以做成判定。

    **为什么要核值，不只核路径。** 设计文件写着「值不在本页」，但它的表格实际上把一批值抄
    在了路径旁边（等级上限、债务本金、委托报酬、招式倍率……）—— 那是可读性要的，不抄的话
    读者得开着 JSON 才看得懂公式。代价是同一个数有两个家，而改 JSON 忘了改正文**不报错**。
    核值把这个代价收掉：抄可以，抄错不行。
    """
    if not DESIGN_DOC.is_file():
        say(f"[FAIL] 找不到设计文件 {DESIGN_DOC.relative_to(ROOT)}")
        return 1
    text = DESIGN_DOC.read_text(encoding="utf-8")
    quoted = set(re.findall(r"`([^`\s]*\.[^`\s]*)`", text))     # 所有带点的反引号片段
    paths = sorted(t for t in quoted if PATH_RE.fullmatch(t))
    # 自报应覆盖量与实际覆盖量：带点却没被路径正则认出来的片段单独列出。
    # 不列的话，正则漏掉一类写法（例如含中文键的路径）会静默少查，而计数看起来还正常 ——
    # 「只处理一部分」的优化必须同时打印两个量，这条坑踩过（踩坑记录 26）。
    unmatched = sorted(t for t in quoted if not PATH_RE.fullmatch(t)
                       and not t.endswith((".md", ".json", ".py", ".godot", ".cs")))
    if not paths:
        say("[FAIL] 设计文件里一个参数路径都没引用，交叉校验等于空转")
        return 1
    missing = [path for path in paths if not _exists(p, path)]
    say(f"路径覆盖量：设计文件里带点的反引号片段 {len(quoted)} 个，"
        f"认出参数路径 {len(paths)} 个，对得上 {len(paths) - len(missing)} 个")
    if missing:
        say(f"[FAIL] 设计文件引用了参数表没有的路径：{missing}")
        return 1
    if unmatched:
        say(f"[FAIL] 有带点片段没被路径正则认出来，可能是漏查："
            f"{unmatched}（要么改写法，要么改 PATH_RE）")
        return 1
    return check_doc_values(p, text)


def check_doc_values(p: Params, text: str) -> int:
    """逐行核对：路径旁边写着的数字必须与参数表对得上。

    判据按行取，因为「写在旁边」在 Markdown 里就是「同一个表格行或同一段」。一行里出现的
    数字不必都是参数（`2000000 铜（200 金）` 的 200 是换算、`6（升级 2 + 训练 4）` 的 2 与 4
    是拆解），所以方向是**从参数表往正文找**，不是反过来：路径的值必须出现在那一行里。

    形状决定判不判得了，三档都自报出来：

    - **标量**：值必须出现在该行 —— 这是主力，覆盖等级上限、本金、利率、倍率这一批。
    - **扁平字典**：每个值都必须出现（`采集 25 / 清理 35 / 护卫 45` 是逐项抄的）。
    - **列表与嵌套结构**：不判。文档按档位或按名只引其中一项（「初级背包 16 格」只提第一
      档），逐个要求会误报。**它们被列出来，不是静默跳过** —— 要把它们纳入判定，得先让
      文档改引具体叶子路径，而那要 PATH_RE 支持中文键。
    """
    checked: list[str] = []
    skipped_no_num: set[str] = set()
    skipped_shape: set[str] = set()
    bad: list[str] = []

    for lineno, line in enumerate(text.splitlines(), 1):
        on_line = sorted({t for t in re.findall(r"`([^`\s]*\.[^`\s]*)`", line)
                          if PATH_RE.fullmatch(t)})
        if not on_line:
            continue
        written = {float(n) for n in BARE_NUM_RE.findall(re.sub(r"`[^`]*`", "", line))}
        for path in on_line:
            want = _checkable_values(p(path))
            if want is None:
                skipped_shape.add(path)
                continue
            if not written:
                skipped_no_num.add(path)
                continue
            checked.append(path)
            absent = sorted(w for w in want if w not in written)
            if absent:
                bad.append(f"第 {lineno} 行 `{path}` 的参数表值 {absent} "
                           f"没出现在该行的数字 {sorted(written)} 里")

    say(f"值覆盖量：核了 {len(checked)} 处路径旁的数字；"
        f"{len(skipped_no_num)} 个路径所在行没写数字（无从核对）；"
        f"{len(skipped_shape)} 个路径的值是列表或嵌套结构（按档位引用，不判）")
    if skipped_shape:
        say(f"[..]   不判值的路径：{sorted(skipped_shape)}")
    if not checked:
        say("[FAIL] 一处数字都没核到，值校验等于空转")
        return 1
    if bad:
        for line in bad:
            say(f"[FAIL] {line}")
        return 1
    say("[OK] 设计文件与参数表没有分叉：路径都在，路径旁的数字也都对得上")
    return 0


def _checkable_values(value) -> set[float] | None:
    """能进值判定的形状返回它该出现的数字集合，判不了的返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return {float(value)}
    if isinstance(value, dict) and value and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values()):
        return {float(v) for v in value.values()}
    return None


def _exists(p: Params, path: str) -> bool:
    try:
        p(path)
        return True
    except ParamError:
        return False


def print_curves(res: SimResult) -> None:
    say(f"\n── 四条曲线 · {res.plan} ──")
    say(f"{'日':>2}  {'时间':>10}  {'精力':>10}  {'现金(铜)':>9}  {'粮食(份)':>9}  备注")
    for r in res.rows:
        say(f"{r.day:>2}  {r.hours_used:>4.1f}/{r.hours_limit:<5.1f}"
            f"  {r.vigor_used:>4}/{r.vigor_limit:<5}"
            f"  {r.copper:>9}  {r.food:>9}  {r.note}")


def _apply_overrides(p: Params, items: list[str]) -> None:
    for item in items:
        path, _, raw = item.partition("=")
        p.override(path, raw)


def flush_log() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = LOG_DIR / f"simulate_week-{stamp}.log"
    n = 2
    while path.exists():        # 同一秒内跑两次不该悄悄覆盖上一次的证据
        path = LOG_DIR / f"simulate_week-{stamp}-{n}.log"
        n += 1
    path.write_text("\n".join(_LINES) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="数值模型七天推演（GP-2）")
    ap.add_argument("--curves", action="store_true", help="额外打出逐日四条曲线")
    ap.add_argument("--plan", help="只跑指定的一份计划")
    ap.add_argument("--set", action="append", default=[], metavar="路径=值",
                    help="临时覆盖一个参数再算，用来撞失败路径；与 --check-doc 同用可撞值校验")
    ap.add_argument("--check-doc", action="store_true",
                    help="只核对设计文件与参数表没有分叉，不跑推演")
    args = ap.parse_args()

    if not PARAMS_PATH.is_file():
        print(f"[FAIL] 找不到参数表 {PARAMS_PATH}")
        print("EXIT=1")
        return 1
    p = Params(json.loads(PARAMS_PATH.read_text(encoding="utf-8")))

    if args.check_doc:
        # --set 也要在这条路径上生效：改一个参数、不改文档，值校验就该报 —— 那是撞它失败
        # 路径的唯一办法，而一个撞不出失败的判定和没有判定是一回事。
        try:
            _apply_overrides(p, args.set)
        except ParamError as exc:
            say(f"[FAIL] {exc.args[0]}")
            say(f"日志 {flush_log().relative_to(ROOT)}")
            print("EXIT=1")
            return 1
        code = check_doc(p)
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print(f"EXIT={code}")
        return code

    try:
        _apply_overrides(p, args.set)

        sheets = analyse_attributes(p)
        say(f"[..]   属性派生：{sheets['lv1'].label} HP {sheets['lv1'].hp}／"
            f"物攻 {sheets['lv1'].patk:.1f}／魔攻 {sheets['lv1'].matk:.1f}；"
            f"{sheets['lvmax'].label} HP {sheets['lvmax'].hp}／"
            f"物攻 {sheets['lvmax'].patk:.1f}／魔攻 {sheets['lvmax'].matk:.1f}")

        names = [args.plan] if args.plan else list(p("week_plan.plans").keys())
        sims = {n: simulate(p, n) for n in names}
        for n, r in sims.items():
            last = r.rows[-1]
            say(f"[..]   推演 {n}：7 天后现金 {last.copper} 铜、粮食 {last.food} 份，"
                f"第一次收获第 {r.first_harvest_day} 天")
        check_premises(p, sims, sheets)
    except ParamError as exc:
        # KeyError 的 str() 会给消息加一层引号，取 args[0] 才是原文。
        say(f"[FAIL] {exc.args[0]}")
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print("EXIT=1")
        return 1

    if args.curves:
        for r in sims.values():
            print_curves(r)

    say("")
    premises = [c for c in CHECKS if c.tag.startswith("P")]
    extra = [c for c in CHECKS if c.tag.startswith("C")]
    for c in CHECKS:
        say(f"{'[OK]  ' if c.ok else '[FAIL]'} {c.tag} {c.name} —— {c.detail}")
        if not c.ok and c.blame:
            say(f"       该改的参数：{c.blame}")

    bad = [c.tag for c in CHECKS if not c.ok]
    say("")
    claims_code = check_doc_claims(len(sims) < len(p("week_plan.plans")))
    # 前提数与判定数不是同一个数：正典给的是六条前提（P1–P6），而 P1 在这里拆成两个判定
    # （P1a 按份逐个判、P1b 判「至少两种成立」）。自报两个数，免得读者对着一个数以为有一处过期。
    premise_ids = {c.tag.rstrip("abcdefghijklmnopqrstuvwxyz") for c in premises}
    say(f"\n覆盖量：读了 {len(p.reads)} 个参数路径；判定 {len(premise_ids)} 条数值前提"
        f"（拆成 {len(premises)} 个判定）+ {len(extra)} 条 PRD 附加约束；"
        f"推演 {len(sims)} 份计划 × {len(next(iter(sims.values())).rows)} 天")
    say(f"结果：{len(CHECKS) - len(bad)}/{len(CHECKS)} 条通过"
        f"／{len(bad)} 条不成立{('：' + '、'.join(bad)) if bad else ''}")
    unjudged = [c.tag for c in CHECKS if "局部范围未判" in c.name]
    failed = bool(bad) or claims_code != 0
    if bad:
        say("[FAIL] 有不成立的判定")
    elif claims_code:
        say("[FAIL] 判定全过，但设计文件正文抄的算出来的量已经过期")
    elif unjudged:
        say(f"[WARN] 只跑了 {len(sims)}/{len(p('week_plan.plans'))} 份计划，"
            f"{unjudged} 未判 —— 这不是一次完整判定，验收要不带 --plan 跑")
    else:
        say("[OK] 全部数值前提与附加约束都成立，正文与算出来的量也一致")
    say(f"日志 {flush_log().relative_to(ROOT)}")
    print(f"EXIT={1 if failed else 0}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
