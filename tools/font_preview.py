#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把中文像素字体渲进 Godot 看实机效果（`ART-2`／[ADR-0008]）。

为什么是入口而不是一次性搭个临时工程：**可读性只能人判**，而人要判的场合不止一次 ——
`ART-2` 判字号，`UI-1` 判逻辑分辨率，`DOC-2` 判界面配色时都得看真字。第一次搭它花掉的
是「哪些属性要设、基线为什么要取整、样本里为什么要混生僻字」这些踩过的坑，重搭一次就
会重踩一次。按 [WORKFLOW §5]「会做第二次的操作写成 `tools/` 下的入口」落成本文。

Godot 工程源码在 `tools/font-preview/`（三个文件，进仓库是为了可复核）；本脚本把它铺到
**工作区根的 `temp/font-preview/`** 再启动 Godot —— 直接在仓库里跑会留下 `.godot/` 缓存。

用法（从设计仓根目录运行）：
    python tools/font_preview.py            # 交互看：←→ 换字体，1/2/3 换分辨率，F 全屏，S 存图
    python tools/font_preview.py --shots    # 自动出图后退出（每个分辨率 × 字体一张 + 一张总表）
    python tools/font_preview.py --clean    # 删掉 temp 下铺开的工程与出图

前置：字体要先在 `temp/font-audit/` 里。没有就先跑 `python tools/audit_fonts.py`。
**缺字体一律判失败，不静默跳过** —— 那会让「没看到字」伪装成「字体没问题」。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_godot import DEFAULT_INSTALL_ROOT        # noqa: E402  同一份安装根目录，不再抄一遍

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "tools" / "font-preview"
WORK_DIR = ROOT.parent / "temp" / "font-preview"
FONT_DIR = ROOT.parent / "temp" / "font-audit"
LOG_DIR = ROOT / "logs"

_LINES: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    _LINES.append(text)


def flush_log() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = LOG_DIR / f"font_preview-{stamp}.log"
    n = 2
    while path.exists():        # 同一秒内跑两次不该悄悄覆盖上一次的证据
        path = LOG_DIR / f"font_preview-{stamp}-{n}.log"
        n += 1
    path.write_text("\n".join(_LINES) + "\n", encoding="utf-8", newline="\n")
    return path


def find_godot() -> Path | None:
    """取标准版（非 mono）的带控制台 exe。

    非 mono 就够：本工程是纯 GDScript，字体光栅化不经过 C#。带控制台那个才接标准输出，
    GUI 版在 Windows 上打不出东西（同 setup_godot.py 里那条注释）。
    """
    if not DEFAULT_INSTALL_ROOT.is_dir():
        return None
    cands = [p for p in DEFAULT_INSTALL_ROOT.rglob("*_console.exe") if "mono" not in p.name]
    return sorted(cands)[0] if cands else None


def stage() -> None:
    """把工程铺到 temp。每次重铺三个源文件，但保留已有的 .godot/ 缓存与 out/。"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(SOURCE_DIR.iterdir()):
        if src.is_file():
            shutil.copy2(src, WORK_DIR / src.name)
            copied.append(src.name)
    say(f"铺开工程到 {WORK_DIR}：{'、'.join(copied)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="中文像素字体的实机可读性对比（ART-2）")
    ap.add_argument("--shots", action="store_true", help="自动出图后退出，不进交互")
    ap.add_argument("--clean", action="store_true", help="删掉 temp 下铺开的工程后退出")
    args = ap.parse_args()

    if args.clean:
        if WORK_DIR.is_dir():
            shutil.rmtree(WORK_DIR)
            print(f"已删除 {WORK_DIR}")
        else:
            print(f"{WORK_DIR} 不存在，无需删除")
        print("EXIT=0")
        return 0

    if not SOURCE_DIR.is_dir():
        say(f"[FAIL] 工程源码不在 {SOURCE_DIR}")
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print("EXIT=1")
        return 1

    ttfs = sorted(FONT_DIR.rglob("*.ttf")) if FONT_DIR.is_dir() else []
    if not ttfs:
        say(f"[FAIL] {FONT_DIR} 里没有字体 —— 先跑 python tools/audit_fonts.py 下载并核授权")
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print("EXIT=1")
        return 1
    say(f"字体目录 {FONT_DIR}：{len(ttfs)} 个 .ttf")

    godot = find_godot()
    if godot is None:
        say(f"[FAIL] 在 {DEFAULT_INSTALL_ROOT} 下找不到 Godot 的 *_console.exe —— "
            f"先跑 python tools/setup_godot.py --check")
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print("EXIT=1")
        return 1
    say(f"Godot {godot}")

    stage()
    cmd = [str(godot), "--path", str(WORK_DIR)]
    if args.shots:
        cmd += ["--", "--shots"]
    say(f"启动：{' '.join(cmd)}")
    # 引擎自己的输出直通终端；工程侧的结论由它写进 out/font-compare.log（UTF-8）。
    code = subprocess.run(cmd, check=False).returncode

    out = WORK_DIR / "out"
    shots = sorted(out.glob("*.png")) if out.is_dir() else []
    say(f"Godot 退出码 {code}｜出图 {len(shots)} 张在 {out}")
    if args.shots and not shots:
        say("[FAIL] 要了出图却一张都没有 —— 退出码不可信，按实际产物判失败")
        say(f"日志 {flush_log().relative_to(ROOT)}")
        print("EXIT=1")
        return 1
    for p in shots:
        say(f"  {p.name}")
    say("看完记得 python tools/font_preview.py --clean")
    say(f"日志 {flush_log().relative_to(ROOT)}")
    print(f"EXIT={0 if code == 0 else 1}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
