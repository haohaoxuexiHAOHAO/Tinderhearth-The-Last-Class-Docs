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
    atk: float = 0.0
    dfn: float = 0.0
    crit: float = 0.0
    dodge: float = 0.0
    atk_speed: float = 0.0
    mitigation: float = 0.0
    effective_hp: float = 0.0

    def power(self, multiplier: float) -> float:
        dps = self.atk * multiplier * self.atk_speed
        return self.effective_hp * dps


def build_sheet(p: Params, label: str, level: int, attrs: dict[str, int]) -> Sheet:
    s = Sheet(label, level, attrs["str"], attrs["agi"], attrs["vit"], attrs["int"])
    s.hp = round(p("derived.hp_base") + p("derived.hp_per_vit") * s.vit)
    s.mp = round(p("derived.mp_base") + p("derived.mp_per_int") * s.int_)
    s.sp = round(p("derived.sp_base") + p("derived.sp_per_vit") * s.vit)
    s.atk = p("derived.atk_base") + p("derived.atk_per_str") * s.str_
    s.dfn = p("derived.def_base") + p("derived.def_per_vit") * s.vit
    k = p("derived.def_softening_k")
    s.mitigation = s.dfn / (s.dfn + k)
    s.effective_hp = s.hp / (1.0 - s.mitigation)
    s.crit = min(p("derived.crit_cap"),
                 p("derived.crit_base") + p("derived.crit_per_agi") * s.agi)
    s.dodge = min(p("derived.dodge_cap"),
                  p("derived.dodge_base") + p("derived.dodge_per_agi") * s.agi)
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
    gap = lvmax.power(ml) / lv1.power(ml)
    lo, hi = p("meta.power_gap_target")
    check("C1", f"战力差落在 {lo}–{hi} 倍",
          lo <= gap <= hi,
          f"满级 ÷ 1 级 = {gap:.2f} 倍"
          f"（有效 HP {lv1.effective_hp:.0f}→{lvmax.effective_hp:.0f}，"
          f"攻击力 {lv1.atk:.1f}→{lvmax.atk:.1f}）",
          "derived.hp_per_vit / derived.atk_per_str / attributes.level_cap")

    # 量级自检：HP 三位数、单次轻攻击伤害两位数（对同级对手）。
    def hit(attacker: Sheet, target: Sheet, mult: float) -> float:
        return max(1.0, attacker.atk * mult * (1.0 - target.mitigation))

    student_start = dict(p("attributes.start_student"))
    st1 = build_sheet(p, "学员 1 级", 1, student_start)
    dmg_lv1 = hit(lv1, st1, ml)
    dmg_max = hit(lvmax, build_sheet(p, "满级学员", cap, spread_points(student_start, (cap - 1) * per)), ml)
    check("C6", "量级：HP 三位数、轻攻击伤害两位数",
          100 <= lv1.hp <= 999 and 100 <= lvmax.hp <= 999
          and 10 <= dmg_lv1 <= 99 and 10 <= dmg_max <= 99,
          f"HP {lv1.hp}→{lvmax.hp}；主角轻攻击伤害 {dmg_lv1:.1f}→{dmg_max:.1f}",
          "derived.hp_base / derived.hp_per_vit / move_multipliers")

    # 主角伤害必须显著低于学员（人物正典：主角低伤辅助，伤害来自学员）。
    ratio = p("move_multipliers.protagonist_light") / p("move_multipliers.student_light")
    check("C4", "主角伤害显著低于学员（轻攻击倍率比 ≤ 0.5）",
          ratio <= 0.5,
          f"主角 {p('move_multipliers.protagonist_light')} ÷ 学员 "
          f"{p('move_multipliers.student_light')} = {ratio:.2f}",
          "move_multipliers.protagonist_light")

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
    atk_mp = p("resources.mp_per_light_hit") * p("resources.light_hits_per_second")
    guard_mp = p("resources.perfect_guard_mp") * p("resources.perfect_guard_opportunities_per_second")
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
    stamina_used: int
    stamina_limit: int
    silver: int
    food: int
    note: str = ""


@dataclass
class SimResult:
    plan: str
    rows: list[DayRow] = field(default_factory=list)
    first_harvest_day: int | None = None
    food_before_first_harvest: int = 0
    overtime_days: list[int] = field(default_factory=list)
    overstamina_days: list[int] = field(default_factory=list)
    negative_cash_days: list[int] = field(default_factory=list)
    negative_food_days: list[int] = field(default_factory=list)
    student_overstamina: list[str] = field(default_factory=list)


def stamina_limit(p: Params, vit: int) -> int:
    """住宿等级从参数表读，不写死在代码里 —— 它是推演的一条假设，藏在函数默认值里
    就看不见了，而看不见的假设正是「参数缺失不许静默补齐」要防的东西。"""
    level = p("week_plan.housing_level_at_start")
    return round(p("stamina.base") + p("stamina.per_vit") * vit
                 + p("stamina.housing_by_level")[level - 1]
                 + p("stamina.meal_full") + p("stamina.health_normal"))


def simulate(p: Params, plan_name: str) -> SimResult:
    plan = p(f"week_plan.plans.{plan_name}")
    res = SimResult(plan_name)

    silver = p("economy.start_silver")
    food = p("economy.start_food")
    students = p("week_plan.students_at_start")
    people = students + 1
    food_per_day = p("economy.food_per_person_per_day") * people

    hero = dict(p("attributes.start_protagonist"))
    hero_limit = stamina_limit(p, hero["vit"])
    stu = dict(p("attributes.start_student"))
    stu_limit = stamina_limit(p, stu["vit"])

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
            cost = crops[crop]["seed_silver"] * cells
            silver -= cost
            growing.append({"crop": crop, "cells": cells,
                            "ready_day": day + crops[crop]["grow_days"]})
            note.append(f"播 {crop}×{cells}（−{cost} 银）")

        # 主角行动
        hours = 0.0
        stamina = 0
        for act in entry["protagonist"]:
            a = p(f"actions.{act}")
            hours += a["hours"]
            stamina += a["stamina"]
            if act.startswith("sortie_"):
                kind = act.split("_", 1)[1]
                reward = p(f"economy.mission_reward_silver.{kind}")
                loot = p(f"economy.mission_loot_expected_silver.{kind}")
                cost = p("economy.consumable_expected_silver_per_sortie")
                injury = p("economy.injury_probability_low_mission") \
                    * p("economy.treatment_fast_silver")
                net = reward + loot - cost - injury
                silver += net
                note.append(f"{kind} 净 +{net:.0f} 银")

        if hours > hours_limit:
            res.overtime_days.append(day)
        if stamina > hero_limit:
            res.overstamina_days.append(day)

        # 学员派工
        for who, job in entry["assignments"].items():
            need = p(f"assignments.{job}.stamina")
            if need > stu_limit:
                res.student_overstamina.append(f"第 {day} 天 {who} 做 {job}")

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
                gain = amount * info["sell_silver"]
                silver += gain
                note.append(f"收 {g['crop']} {amount} 份卖 +{gain} 银")
            growing.remove(g)

        # 吃饭
        food -= food_per_day
        if food < 0:
            res.negative_food_days.append(day)
        if silver < 0:
            res.negative_cash_days.append(day)

        res.rows.append(DayRow(day, hours, hours_limit, stamina, hero_limit,
                               round(silver), food, "；".join(note)))
    return res


# ── 六条数值前提 ──────────────────────────────────────────────────────
def check_premises(p: Params, sims: dict[str, SimResult], sheets: dict) -> None:
    # P1：19 游戏小时装得下，且至少两种成立的一日安排。
    # 「至少两种」这半条只有在跑了全部计划时才判得了；只跑一份时它必然不成立，
    # 那种失败与数值无关，报出来只会训练人忽略 FAIL。所以局部范围里改判「跑过的都成立」，
    # 并在判定文字里写明这一轮没覆盖哪半条。
    feasible = [name for name, r in sims.items()
                if not r.overtime_days and not r.overstamina_days
                and not r.student_overstamina]
    broken = {n: {"超时": r.overtime_days, "超体力": r.overstamina_days,
                  "学员超体力": r.student_overstamina}
              for n, r in sims.items() if n not in feasible}
    total_plans = len(p("week_plan.plans"))
    partial = len(sims) < total_plans
    # 跑过的计划本身超时超体力，是真失败，局部范围也照判。
    check("P1a", "跑过的每份安排都装得进 19 小时与体力上限",
          not broken,
          f"跑了 {list(sims)}；成立 {feasible}；不成立 {broken}",
          "actions 一节的 hours 与 stamina / stamina.per_vit")
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
    buffer_days = ref.food_before_first_harvest / per_day if per_day else 0
    ok3 = (not ref.negative_food_days and not ref.negative_cash_days
           and 1.0 <= buffer_days <= 2.0 and ref.first_harvest_day is not None)
    check("P3", "撑到第一次收获且不断粮，收获时仍余 1–2 天缓冲",
          ok3,
          f"按计划「{ref.plan}」：第一次收获在第 {ref.first_harvest_day} 天，收获前余 "
          f"{ref.food_before_first_harvest} 份 = {buffer_days:.2f} 天；"
          f"断粮日 {ref.negative_food_days}，现金为负日 {ref.negative_cash_days}",
          "economy.start_food / economy.start_silver / farm.crops.*.grow_days")

    # P4：一次低难度委托的报酬 ÷ 时间与体力消耗
    lines = []
    ok4 = True
    for kind in ("gather", "clear", "escort"):
        a = p(f"actions.sortie_{kind}")
        reward = p(f"economy.mission_reward_silver.{kind}")
        loot = p(f"economy.mission_loot_expected_silver.{kind}")
        net = reward + loot - p("economy.consumable_expected_silver_per_sortie") \
            - p("economy.injury_probability_low_mission") * p("economy.treatment_fast_silver")
        day_food = p("economy.food_per_person_per_day") \
            * (p("week_plan.students_at_start") + 1) * p("economy.food_buy_silver")
        good = net > 0 and net >= day_food
        ok4 = ok4 and good
        lines.append(f"{kind} 净 {net:.0f} 银／{a['hours']}h／{a['stamina']}EN "
                     f"= {net / a['hours']:.1f} 银每小时、{net / a['stamina']:.2f} 银每点体力"
                     f"（全队一天粮食成本 {day_food} 银）{'' if good else ' ← 不足'}")
    check("P4", "低难度委托净收益为正，且不低于全队一天的粮食成本",
          ok4, "；".join(lines),
          "economy.mission_reward_silver / economy.mission_loot_expected_silver")

    # P5：治疗费用 ÷ 委托报酬
    treat = p("economy.treatment_fast_silver")
    low_reward = p("economy.mission_reward_silver.gather")
    ratio = treat / low_reward
    slow, fast_d = p("economy.treatment_slow_days"), p("economy.treatment_fast_days")
    check("P5", "花钱快治是真选项（治疗费 ≤ 低难度报酬的 2 倍，且省下的天数 ≥ 2）",
          ratio <= 2.0 and (slow - fast_d) >= 2,
          f"治疗费 {treat} ÷ 采集报酬 {low_reward} = {ratio:.2f} 倍；"
          f"慢养 {slow} 天 vs 快治 {fast_d} 天，省 {slow - fast_d} 天",
          "economy.treatment_fast_silver / economy.treatment_slow_days")

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
                revenue += batch * c["sell_silver"] * demand * supply
                sold += batch
            total += revenue - c["seed_silver"] * cells
        return total

    best_base = max(crops, key=lambda n: crops[n]["sell_silver"])
    others = [n for n in crops if n != best_base]
    pref_pick = max(others, key=lambda n: season_income(n, True))
    income_pref = season_income(pref_pick, True)
    income_base = season_income(best_base, False)
    check("P6", "偏好溢价足以让「按偏好种」优于「按最高基础价种」",
          income_pref > income_base,
          f"按偏好种 {pref_pick} 一季 {income_pref:.0f} 银 > "
          f"按最高基础价种 {best_base} 一季 {income_base:.0f} 银"
          f"（溢价 {pref}，批量阈值 {thr}，每档递减 {decay}）",
          "pricing.demand_preferred / pricing.supply_step_decay")

    # 附加：第二季利息不得压过前期收入
    principal = p("economy.debt_principal_silver")
    rate = p("economy.debt_quarterly_rate")
    interest = principal * rate
    per_day_interest = interest / p("time.season_days")
    check("C8", "第二季利息折到每天不超过一条低难度委托报酬的一半",
          per_day_interest <= low_reward * 0.5,
          f"本金 {principal} 银 × {rate} = 一季 {interest:.0f} 银 = 每天 "
          f"{per_day_interest:.1f} 银；采集报酬 {low_reward} 银",
          "economy.debt_principal_silver / economy.debt_quarterly_rate")

    # 附加：两条长期目标（练满与还清债务）必须落在同一量级，否则先到的那条会让另一条失去意义
    best = max(sims.values(), key=lambda r: r.rows[-1].silver)
    days = len(best.rows)
    net_per_day = (best.rows[-1].silver - p("economy.start_silver")) / days
    days_to_repay = principal / net_per_day if net_per_day > 0 else float("inf")
    sorties = sheets["sorties_to_cap"]
    sorties_per_day = 1.5
    days_to_cap = sorties / sorties_per_day
    ratio_goals = days_to_cap / days_to_repay if days_to_repay else float("inf")
    check_cross_plan(
        partial, "C9", "练满与还清债务落在同一量级（天数比 0.5–2 倍）",
        0.5 <= ratio_goals <= 2.0,
        f"满级需 {sheets['total_exp']:.0f} 经验 = {sorties:.0f} 次低难度出征 ≈ "
        f"{days_to_cap:.0f} 天（按每天 {sorties_per_day} 次）；还债需 {days_to_repay:.0f} 天"
        f"（按「{best.plan}」的日净收入 {net_per_day:.1f} 银）；比 {ratio_goals:.2f}",
        "growth.exp_curve_base / growth.exp_curve_exponent / economy.debt_principal_silver",
        "还债天数按收入最高的那份计划算，只跑一份时这个基准是任意的")

    # 附加：容量必须造成一次取舍，但不频繁被迫丢弃
    kinds = p("capacity.expected_sortie_item_kinds")
    slots = p("capacity.backpack_slots_by_level")[0]
    check("C7", "一次出征的产出种类接近但不超过初级背包格数（造成取舍而非频繁丢弃）",
          slots * 0.7 <= kinds <= slots,
          f"一次出征约 {kinds} 种物品，初级背包 {slots} 格，占用 {kinds / slots:.0%}",
          "capacity.backpack_slots_by_level / capacity.expected_sortie_item_kinds")


# ── 输出 ──────────────────────────────────────────────────────────────
def check_doc(p: Params) -> int:
    """核对设计文件里出现的每个参数路径都在参数表里存在。

    为什么需要它：设计文件解释公式、参数表持有值，两处必然一起改。人工核对「文档里提到的
    参数还在不在」是那种没人会真做第二次的事，所以做成判定。**它只查路径存在性**，不查
    正文里的数字 —— 正文刻意不重复值，值只在 JSON 里，这样就没有第二份会漂移的数字。
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
    say(f"覆盖量：设计文件里带点的反引号片段 {len(quoted)} 个，"
        f"认出参数路径 {len(paths)} 个，对得上 {len(paths) - len(missing)} 个")
    if missing:
        say(f"[FAIL] 设计文件引用了参数表没有的路径：{missing}")
        return 1
    if unmatched:
        say(f"[FAIL] 有带点片段没被路径正则认出来，可能是漏查："
            f"{unmatched}（要么改写法，要么改 PATH_RE）")
        return 1
    say("[OK] 设计文件与参数表没有分叉")
    return 0


def _exists(p: Params, path: str) -> bool:
    try:
        p(path)
        return True
    except ParamError:
        return False


def print_curves(res: SimResult) -> None:
    say(f"\n── 四条曲线 · {res.plan} ──")
    say(f"{'日':>2}  {'时间':>10}  {'体力':>10}  {'现金(银)':>9}  {'粮食(份)':>9}  备注")
    for r in res.rows:
        say(f"{r.day:>2}  {r.hours_used:>4.1f}/{r.hours_limit:<5.1f}"
            f"  {r.stamina_used:>4}/{r.stamina_limit:<5}"
            f"  {r.silver:>9}  {r.food:>9}  {r.note}")


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
                    help="临时覆盖一个参数再算，用来撞失败路径")
    ap.add_argument("--check-doc", action="store_true",
                    help="只核对设计文件与参数表没有分叉，不跑推演")
    args = ap.parse_args()

    if not PARAMS_PATH.is_file():
        print(f"[FAIL] 找不到参数表 {PARAMS_PATH}")
        print("EXIT=1")
        return 1
    p = Params(json.loads(PARAMS_PATH.read_text(encoding="utf-8")))

    if args.check_doc:
        code = check_doc(p)
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print(f"EXIT={code}")
        return code

    try:
        for item in args.set:
            path, _, raw = item.partition("=")
            p.override(path, raw)

        sheets = analyse_attributes(p)
        say(f"[..]   属性派生：{sheets['lv1'].label} HP {sheets['lv1'].hp}／"
            f"攻击 {sheets['lv1'].atk:.1f}；{sheets['lvmax'].label} HP {sheets['lvmax'].hp}／"
            f"攻击 {sheets['lvmax'].atk:.1f}")

        names = [args.plan] if args.plan else list(p("week_plan.plans").keys())
        sims = {n: simulate(p, n) for n in names}
        for n, r in sims.items():
            last = r.rows[-1]
            say(f"[..]   推演 {n}：7 天后现金 {last.silver} 银、粮食 {last.food} 份，"
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
    say(f"\n覆盖量：读了 {len(p.reads)} 个参数路径；判定 {len(premises)} 条数值前提 + "
        f"{len(extra)} 条 PRD 附加约束；推演 {len(sims)} 份计划 × "
        f"{len(next(iter(sims.values())).rows)} 天")
    say(f"结果：{len(CHECKS) - len(bad)}/{len(CHECKS)} 条通过"
        f"／{len(bad)} 条不成立{('：' + '、'.join(bad)) if bad else ''}")
    unjudged = [c.tag for c in CHECKS if "局部范围未判" in c.name]
    if bad:
        say("[FAIL] 有不成立的判定")
    elif unjudged:
        say(f"[WARN] 只跑了 {len(sims)}/{len(p('week_plan.plans'))} 份计划，"
            f"{unjudged} 未判 —— 这不是一次完整判定，验收要不带 --plan 跑")
    else:
        say("[OK] 全部数值前提与附加约束都成立")
    say(f"日志 {flush_log().relative_to(ROOT)}")
    print(f"EXIT={1 if bad else 0}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
