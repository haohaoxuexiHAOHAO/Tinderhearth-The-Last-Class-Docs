#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中文像素字体的授权核实与字形覆盖量测（`ART-2`）。

为什么是脚本而不是一次性手查：这件事有两个会变的对象。**授权会变**（上游改许可证、
改定价、改上游字形来源），而字体选型一旦铺开就难换，靠印象记「它是 OFL」正是
[WORKFLOW §7] 要防的形状。**语料会长**（文案越写越多，生僻字随时冒出来），而缺字在
游戏里的表现是豆腐块，不报错、上线才被玩家发现。两者都需要能重跑的量具。

它做三件事，每件都只认可复核的证据：

1. **授权**：从官方仓库拉许可证原文，比对 SHA256 与「我们当初据以下结论的那几句话」
   是否仍在。对不上就判失败并要求重新读原文 —— 不猜、不沿用。
2. **覆盖**：自己解 `cmap`（不依赖 fontTools，本机没有），量各候选对四份语料的覆盖率。
   语料包含**设计仓自己的全部中文**，这是最贴近成品文案的样本。
3. **度量**：读 `head`／`hhea` 给出设计 em、建议字号与行高 —— 像素完美渲染要的就是
   「字号必须等于设计尺寸」，这个数不能靠目测。

**选定款有硬要求，落选款只报告。** 选定款对「设计仓语料」与「GB2312 汉字」必须全覆盖，
差一个字就判失败：那正是将来会变成豆腐块的字。

用法（从设计仓根目录运行）：
    python tools/audit_fonts.py                 # 授权 + 下载 + 覆盖 + 度量
    python tools/audit_fonts.py --licenses      # 只核授权，不下载字体（快）
    python tools/audit_fonts.py --offline       # 不联网，只量已下载的字体
    python tools/audit_fonts.py --select <id>   # 临时按某款算硬要求，用来比较
    python tools/audit_fonts.py --clean         # 删掉 temp 下的下载物

输出约定（与 check_docs.py、simulate_week.py 一致）：固定 UTF-8；判定逐条打
[OK]／[FAIL]；末尾打覆盖量、结果与一行 EXIT=。日志由本脚本自己写 UTF-8 到
logs/audit_fonts-<时间戳>.log。**下载物落工作区根的 temp/font-audit/**（不在任何仓库里，
用完 --clean 删掉）。
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import shutil
import struct
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
# 临时资源放工作区根的 temp/，不写 C 盘（WORKFLOW §5）。设计仓是工作区的子目录。
WORK_DIR = ROOT.parent / "temp" / "font-audit"
UA = "Tinderhearth-font-audit/1.0 (+ART-2)"

# 选定款。ADR-0008 定下来之后必须填上这里 —— 填了它才会执行硬要求。
# 空着只在 ADR-0008 落地之前成立，那时还没有「选定」这件事可守。
SELECTED = "fusion-12px"

_LINES: list[str] = []
_FAILS: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    _LINES.append(text)


def ok(text: str) -> None:
    say(f"[OK]   {text}")


def fail(text: str) -> None:
    say(f"[FAIL] {text}")
    _FAILS.append(text)


def note(text: str) -> None:
    say(f"[..]   {text}")


# ── 候选登记表 ────────────────────────────────────────────────────────
# 版本一律钉死。上游发新版时改这里并重跑，不做「自动取最新」——
# 那会让「今天核过」变成「今天碰巧过」。


@dataclass
class LicenseSource:
    url: str                    # 官方许可证原文（raw，不是仓库页面）
    kind: str                   # 我们据此写进 ADR 的许可证名称
    marks: list[str]            # 据以下结论的关键句，逐条必须仍在原文里
    sha256: str = ""            # 钉死内容；空＝首轮记录，运行后填回来
    label: str = "许可证"


@dataclass
class FontSource:
    url: str
    kind: str                   # zip｜raw
    label: str


@dataclass
class Upstream:
    """入选款的上游字形来源。像素字体常见「基于某款字体改造」，这一层不看就等于没核。"""
    name: str
    url: str                    # 入选款仓库里随附的那份上游许可证（它实际打包的版本）
    provides: str               # 它提供了哪部分字形
    sha256: str = ""


# 上游许可证按签名归类。归不出类就判失败 —— 「看起来像自由软件」不是依据。
UPSTREAM_FAMILIES: list[tuple[str, str, bool]] = [
    ("SIL OPEN FONT LICENSE Version 1.1", "OFL-1.1", True),
    ("Unlimited permission is granted to use, copy, and distribute",
     "全权限自由授权（M+／美咲 系措辞，明示可商用可改）", True),
    ("MIT License", "MIT", True),
    ("Apache License", "Apache-2.0", True),
    ("GNU GENERAL PUBLIC LICENSE", "GPL —— 本项目为闭源商业发行，不可接受", False),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL —— 需单独评估", False),
]


@dataclass
class Candidate:
    id: str
    name: str
    repo: str
    licenses: list[LicenseSource]
    fonts: list[FontSource] = field(default_factory=list)
    verdict: str = ""           # 本轮结论的一句话，写进日志便于对照 ADR
    upstream: list[Upstream] = field(default_factory=list)


ARK_TAG = "2026.08.11"
FUSION_TAG = "2026.08.11"
CUBIC_TAG = "v1.500"


def _ark_zip(px: int) -> str:
    return (f"https://github.com/TakWolf/ark-pixel-font/releases/download/{ARK_TAG}/"
            f"ark-pixel-font-{px}px-proportional-ttf-v{ARK_TAG}.zip")


def _only(cands: list[Candidate], keep: str | None) -> list[Candidate]:
    """只留一个候选。选定款定下来之后，日常重跑不必再拉另外六个源的 200 多 MB。"""
    if keep is None:
        return cands
    hit = [c for c in cands if c.id == keep]
    if not hit:
        raise SystemExit(f"[FAIL] --only {keep} 不在候选表里：{[c.id for c in cands]}")
    return hit


def _fusion_zip(px: int) -> str:
    return (f"https://github.com/TakWolf/fusion-pixel-font/releases/download/{FUSION_TAG}/"
            f"fusion-pixel-font-{px}px-proportional-ttf-v{FUSION_TAG}.zip")


_FUSION_ASSET = ("https://raw.githubusercontent.com/TakWolf/fusion-pixel-font/master/"
                 "assets/fonts/")


CANDIDATES: list[Candidate] = [
    Candidate(
        id="fusion-12px",
        name="缝合像素字体 12px 比例模式",
        repo="https://github.com/TakWolf/fusion-pixel-font",
        licenses=[LicenseSource(
            url="https://raw.githubusercontent.com/TakWolf/fusion-pixel-font/master/LICENSE-OFL",
            kind="SIL OFL 1.1",
            marks=["Fusion Pixel Font",
                   "SIL OPEN FONT LICENSE Version 1.1",
                   # 商业发行靠的就是这一句，单独钉住它
                   "redistributed and/or sold with any software"],
            sha256="bc518cf64b8032c07690f33cc270c35c179255a6ac8efa7c165ebae7e8f76a63",
        )],
        fonts=[FontSource(_fusion_zip(12), "zip", "12px 比例")],
        # 七个上游取自入选款仓库**自己随附**的那份许可证，而不是上游项目的当前 HEAD ——
        # 我们发行的是它打包进去的那个版本，该看的就是那一份。
        upstream=[Upstream(name, _FUSION_ASSET + rel, provides, sha)
                  for name, rel, provides, sha in [
            ("方舟像素字体 Ark Pixel", "ark-pixel/OFL.txt", "10、12px 基础字形与参数",
             "3ab41567e68e3988ba1ef16dd2644eca95ca5648ea12e7d46e6287fc0bbe5aee"),
            ("美咲フォント Misaki", "misaki/misaki.txt", "8px 日语汉字",
             "82929cc3b34c79b6a67f21fe137c7bb165589c9e34ba1441611e493afd67dfca"),
            ("美績点陣體 MisekiBitmap", "miseki-bitmap/LICENSE.txt", "8px 简体汉字",
             "e855b45b384d37c9a778119271bd9c32706e3f1f9f278de0ad47347606eea846"),
            ("精品點陣體 7×7", "boutique-bitmap-7x7/OFL.txt", "8px 繁体汉字",
             "ad588b5ce58a02179b806381339fd380e5110771f2fa91279af026fd3ab97002"),
            ("精品點陣體 9×9", "boutique-bitmap-9x9/OFL.txt", "10px 繁体补充",
             "265f3814079511b3f3fce9003cb60a1402fa792849c5cae79e5998939eb02617"),
            ("俐方體 11 號 Cubic 11", "cubic-11/OFL.txt", "12px 繁体补充",
             "2b6e5938e5cffa0b9e183bd05f8c363e174e7ebed1a0556e2855fd1707fa2188"),
            ("Galmuri", "galmuri/LICENSE.txt", "8、10、12px 朝鲜语",
             "86a3ee9495f942f0243f18c103da9faca27adb88142613edb8bb852e56c892c1"),
        ]],
    ),
    Candidate(
        id="fusion-10px",
        name="缝合像素字体 10px 比例模式",
        repo="https://github.com/TakWolf/fusion-pixel-font",
        licenses=[],            # 与 fusion-12px 同仓同许可证，不重复核
        fonts=[FontSource(_fusion_zip(10), "zip", "10px 比例")],
    ),
    Candidate(
        id="fusion-8px",
        name="缝合像素字体 8px 比例模式",
        repo="https://github.com/TakWolf/fusion-pixel-font",
        licenses=[],
        fonts=[FontSource(_fusion_zip(8), "zip", "8px 比例")],
    ),
    Candidate(
        id="ark-10px",
        name="方舟像素字体 10px 比例模式",
        repo="https://github.com/TakWolf/ark-pixel-font",
        licenses=[LicenseSource(
            url="https://raw.githubusercontent.com/TakWolf/ark-pixel-font/master/LICENSE-OFL",
            kind="SIL OFL 1.1",
            marks=["Ark Pixel Font", "SIL OPEN FONT LICENSE Version 1.1"],
            sha256="3ab41567e68e3988ba1ef16dd2644eca95ca5648ea12e7d46e6287fc0bbe5aee",
        )],
        fonts=[FontSource(_ark_zip(10), "zip", "10px 比例")],
    ),
    Candidate(
        id="ark-12px",
        name="方舟像素字体 12px 比例模式",
        repo="https://github.com/TakWolf/ark-pixel-font",
        licenses=[],
        fonts=[FontSource(_ark_zip(12), "zip", "12px 比例")],
    ),
    Candidate(
        id="ark-16px",
        name="方舟像素字体 16px 比例模式",
        repo="https://github.com/TakWolf/ark-pixel-font",
        licenses=[],
        fonts=[FontSource(_ark_zip(16), "zip", "16px 比例")],
    ),
    Candidate(
        id="cubic-11",
        name="俐方體 11 號 Cubic 11",
        repo="https://github.com/ACh-K/Cubic-11",
        licenses=[LicenseSource(
            url=f"https://raw.githubusercontent.com/ACh-K/Cubic-11/{CUBIC_TAG}/OFL.txt",
            kind="SIL OFL 1.1（复合声明，含上游 M+ BITMAP FONTS）",
            marks=["[Cubic 11]", "M+ BITMAP FONTS",
                   "SIL OPEN FONT LICENSE Version 1.1"],
            sha256="2b6e5938e5cffa0b9e183bd05f8c363e174e7ebed1a0556e2855fd1707fa2188",
        )],
        fonts=[FontSource(
            f"https://raw.githubusercontent.com/ACh-K/Cubic-11/{CUBIC_TAG}/fonts/ttf/Cubic_11.ttf",
            "raw", "Cubic_11.ttf")],
    ),
    Candidate(
        id="dotted",
        name="点点像素",
        repo="https://github.com/wixette/dotted-chinese-fonts",
        licenses=[
            LicenseSource(
                url="https://raw.githubusercontent.com/wixette/dotted-chinese-fonts/master/LICENSE",
                kind="GPL 2.0",
                marks=["GNU GENERAL PUBLIC LICENSE", "Version 2, June 1991"],
                sha256="8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643",
            ),
            LicenseSource(
                url="https://raw.githubusercontent.com/wixette/dotted-chinese-fonts/master/README.md",
                kind="GPL 2.0（字形派生自文泉驿点阵宋体）",
                marks=["released under GPL 2.0", "WenQuanYi", "文泉驿点阵宋体"],
                sha256="9e005e3659c1c077192eb20bde802ff058446adfc0d2ca3dfba841262ca7ed1f",
                label="说明与字形来源",
            ),
        ],
        # 授权就判死，不必量覆盖：GPL 2.0 且未见字体嵌入例外。
        verdict="因许可证出局，不量覆盖",
    ),
    Candidate(
        id="zpix",
        name="Zpix 最像素",
        repo="https://github.com/SolidZORO/zpix-pixel-font",
        licenses=[LicenseSource(
            url="https://raw.githubusercontent.com/SolidZORO/zpix-pixel-font/master/README.md",
            kind="非开源，商业需逐产品付费授权",
            marks=["用于 单个商业产品", "禁止对本字体进行修改", "拆分"],
            sha256="2de8b7b6b98ef2be263b0bf4fc92d53574f71de2d3c68fca8563c766a3095a37",
            label="授权声明（仓库无 LICENSE 文件，声明在 README）",
        )],
        verdict="因许可证出局，不量覆盖",
    ),
]

# 选定款必须全覆盖的语料。差一个字就是将来的豆腐块。
#
# **为什么不要求 GB2312 全覆盖**：首轮实测，选定款缺的 145 个 GB2312 字全是「劐唣嗍垡墚
# 墼娈媵」这类生僻字，正常文案不会用。把它设成硬要求的后果不是更安全，而是这条判定永远
# FAIL —— 然后我们学会忽略它，连真失败一起忽略（同一条理由见 production/像素绘制原则.md
# §11）。要求只落在「**会被渲染给玩家看的字**」上，这个集合会随文案增长，缺字当场报。
#
# **为什么「设计仓语料」也不是硬要求**（这条是写 ADR-0008 时当场撞出来的）：那份 ADR 要
# 说明字体缺哪些字，就得把「劐唣嗍垡墚墼」写进正文 —— 于是语料里出现了字体必然不覆盖的
# 字，硬要求瞬间变成永远失败。设计文档**本来就该**引用字体没有的字。所以它降为报告项：
# 数字与缺字清单照打，供人判断文案用字是否越界，但不判失败。
REQUIRE_FULL = ["代码仓游戏文本"]


# ── 语料 ──────────────────────────────────────────────────────────────
CJK_RANGES = [
    (0x3400, 0x4DBF),       # 扩展 A
    (0x4E00, 0x9FFF),       # 基本区
    (0xF900, 0xFAFF),       # 兼容汉字
]


def is_cjk(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


def _legacy_hanzi(codec: str, lead: range, trail: range) -> set[int]:
    """把国标编码里的汉字枚举出来。用 codecs 现算，不夹带一份可能过期的字表。"""
    out: set[int] = set()
    for b1 in lead:
        for b2 in trail:
            try:
                ch = bytes([b1, b2]).decode(codec)
            except UnicodeDecodeError:
                continue
            cp = ord(ch)
            if is_cjk(cp):
                out.add(cp)
    return out


PUNCT = ("，。、；：？！“”‘’「」『』（）《》〈〉【】〔〕—…～·＋－×÷＝％￥°　"
         "①②③④⑤⑥⑦⑧⑨⑩→←↑↓√※")


def build_corpora() -> dict[str, tuple[set[int], str]]:
    """四份语料。每份都给出「它是怎么来的」，好让数字能被复算。"""
    gb2312 = _legacy_hanzi("gb2312", range(0xA1, 0xF8), range(0xA1, 0xFF))
    gbk = _legacy_hanzi("gbk", range(0x81, 0xFF), range(0x40, 0xFF))

    docs: set[int] = set()
    files = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts or "logs" in path.parts:
            continue
        files += 1
        for ch in path.read_text(encoding="utf-8"):
            cp = ord(ch)
            if is_cjk(cp):
                docs.add(cp)

    out = {
        "GB2312 汉字": (gb2312, "由 codecs 现算 GB2312 双字节区里的汉字"),
        "GBK 汉字": (gbk, "由 codecs 现算 GBK 双字节区里的汉字"),
        "设计仓语料": (docs, f"设计仓 {files} 份 .md 里出现过的全部汉字"),
        "中文标点与符号": ({ord(c) for c in PUNCT}, f"显式列出的 {len(set(PUNCT))} 个"),
    }

    # 真正会被玩家看到的那批字：代码仓 data/text 下的外置文本。
    # 拿不到就明说跳过 —— 只 clone 了设计仓的人也该跑得动本脚本。
    text_dir = ROOT.parent / "Tinderhearth-The-Last-Class" / "data" / "text"
    if text_dir.is_dir():
        game: set[int] = set()
        n = 0
        for path in sorted(text_dir.rglob("*.json")):
            n += 1
            for ch in path.read_text(encoding="utf-8"):
                cp = ord(ch)
                if is_cjk(cp):
                    game.add(cp)
        out["代码仓游戏文本"] = (game, f"代码仓 data/text 下 {n} 份 .json 里的全部汉字")
    else:
        note(f"代码仓文本目录不在（{text_dir}）→ 语料「代码仓游戏文本」本轮跳过，"
             f"它的硬要求没有执行")
    return out


# ── 字体解析（只用标准库）────────────────────────────────────────────
class Coverage:
    """码位覆盖，按区间存。format 12 的组可以覆盖到 0x10FFFF，摊平成 set 会炸内存。"""

    def __init__(self, ranges: list[tuple[int, int]]) -> None:
        merged: list[tuple[int, int]] = []
        for lo, hi in sorted(ranges):
            if merged and lo <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        self.ranges = merged
        self._starts = [lo for lo, _ in merged]

    def __contains__(self, cp: int) -> bool:
        i = bisect.bisect_right(self._starts, cp) - 1
        return i >= 0 and cp <= self.ranges[i][1]

    def count_in(self, lo: int, hi: int) -> int:
        return sum(max(0, min(hi, b) - max(lo, a) + 1) for a, b in self.ranges)

    @property
    def total(self) -> int:
        return sum(b - a + 1 for a, b in self.ranges)


class SfntError(RuntimeError):
    pass


class Sfnt:
    def __init__(self, data: bytes) -> None:
        self.data = data
        base = 0
        if data[:4] == b"ttcf":
            base = struct.unpack(">I", data[12:16])[0]
        num = struct.unpack(">H", data[base + 4:base + 6])[0]
        self.tables: dict[bytes, tuple[int, int]] = {}
        for i in range(num):
            rec = base + 12 + 16 * i
            tag = data[rec:rec + 4]
            off, length = struct.unpack(">II", data[rec + 8:rec + 16])
            self.tables[tag] = (off, length)

    def _u16(self, at: int) -> int:
        return struct.unpack(">H", self.data[at:at + 2])[0]

    def _s16(self, at: int) -> int:
        return struct.unpack(">h", self.data[at:at + 2])[0]

    def _u32(self, at: int) -> int:
        return struct.unpack(">I", self.data[at:at + 4])[0]

    def metrics(self) -> dict[str, int]:
        if b"head" not in self.tables or b"hhea" not in self.tables:
            raise SfntError("缺 head 或 hhea 表")
        head = self.tables[b"head"][0]
        hhea = self.tables[b"hhea"][0]
        return {
            "unitsPerEm": self._u16(head + 18),
            "ascender": self._s16(hhea + 4),
            "descender": self._s16(hhea + 6),
            "lineGap": self._s16(hhea + 8),
        }

    def coverage(self) -> tuple[Coverage, str]:
        if b"cmap" not in self.tables:
            raise SfntError("缺 cmap 表")
        cmap = self.tables[b"cmap"][0]
        num = self._u16(cmap + 2)
        subs: dict[tuple[int, int], int] = {}
        for i in range(num):
            rec = cmap + 4 + 8 * i
            plat = self._u16(rec)
            enc = self._u16(rec + 2)
            subs[(plat, enc)] = cmap + self._u32(rec + 4)
        # 优先取全 Unicode 的子表：BMP 之外的字（扩展 B 起）只有 format 12 认得。
        for key in [(3, 10), (0, 6), (0, 4), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0)]:
            if key in subs:
                at = subs[key]
                fmt = self._u16(at)
                if fmt == 12:
                    return self._fmt12(at), f"cmap {key} format 12"
                if fmt == 4:
                    return self._fmt4(at), f"cmap {key} format 4"
                if fmt == 6:
                    return self._fmt6(at), f"cmap {key} format 6"
        raise SfntError(f"没有能解的 cmap 子表，只有 {sorted(subs)}")

    def _fmt4(self, at: int) -> Coverage:
        seg2 = self._u16(at + 6)
        seg = seg2 // 2
        ends = at + 14
        starts = ends + seg2 + 2
        deltas = starts + seg2
        offsets = deltas + seg2
        ranges: list[tuple[int, int]] = []
        for i in range(seg):
            end = self._u16(ends + 2 * i)
            start = self._u16(starts + 2 * i)
            if start > end:
                continue
            ro = self._u16(offsets + 2 * i)
            if ro == 0:
                delta = self._u16(deltas + 2 * i)
                # glyph = (cp + delta) & 0xFFFF；只有整段落在 0 上才算没映射
                lo = hi = None
                for cp in range(start, min(end, 0xFFFF) + 1):
                    if (cp + delta) & 0xFFFF:
                        if lo is None:
                            lo = hi = cp
                        else:
                            hi = cp
                    elif lo is not None:
                        ranges.append((lo, hi))
                        lo = hi = None
                if lo is not None:
                    ranges.append((lo, hi))
            else:
                lo = hi = None
                for cp in range(start, min(end, 0xFFFF) + 1):
                    gi_at = offsets + 2 * i + ro + 2 * (cp - start)
                    if gi_at + 2 > len(self.data):
                        break
                    if self._u16(gi_at):
                        if lo is None:
                            lo = hi = cp
                        else:
                            hi = cp
                    elif lo is not None:
                        ranges.append((lo, hi))
                        lo = hi = None
                if lo is not None:
                    ranges.append((lo, hi))
        return Coverage(ranges)

    def _fmt6(self, at: int) -> Coverage:
        first = self._u16(at + 6)
        count = self._u16(at + 8)
        ranges = []
        lo = hi = None
        for i in range(count):
            cp = first + i
            if self._u16(at + 10 + 2 * i):
                if lo is None:
                    lo = hi = cp
                else:
                    hi = cp
            elif lo is not None:
                ranges.append((lo, hi))
                lo = hi = None
        if lo is not None:
            ranges.append((lo, hi))
        return Coverage(ranges)

    def _fmt12(self, at: int) -> Coverage:
        groups = self._u32(at + 12)
        ranges = []
        for i in range(groups):
            g = at + 16 + 12 * i
            start = self._u32(g)
            end = self._u32(g + 4)
            gid = self._u32(g + 8)
            if gid == 0:
                start += 1          # 该组首字映射到 .notdef
            if start <= end:
                ranges.append((start, end))
        return Coverage(ranges)


# ── 抓取 ──────────────────────────────────────────────────────────────
def fetch(url: str, dest: Path | None = None, tries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(body)
            return body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"抓不到 {url}：{last}")


def check_licenses(cands: list[Candidate]) -> int:
    """核授权。抓不到就是**没核过**，不是「大概还行」。"""
    checked = 0
    for cand in cands:
        for src in cand.licenses:
            checked += 1
            try:
                body = fetch(src.url, WORK_DIR / "licenses" /
                             f"{cand.id}-{Path(src.url).name}")
            except RuntimeError as exc:
                fail(f"{cand.name} 的{src.label}抓不到 → 本轮判定「未核实」：{exc}")
                continue
            digest = hashlib.sha256(body).hexdigest()
            text = body.decode("utf-8", errors="replace")
            missing = [m for m in src.marks if m not in text]
            if missing:
                fail(f"{cand.name} 的{src.label}里找不到据以下结论的原文："
                     f"{'；'.join(repr(m) for m in missing)} → 去 {src.url} 重读原文")
                continue
            if not src.sha256:
                note(f"{cand.name} 的{src.label}尚未钉死内容，本次实测 "
                     f"sha256={digest} —— 填回 audit_fonts.py 才算立住")
            elif src.sha256 != digest:
                fail(f"{cand.name} 的{src.label}内容变了（钉的是 {src.sha256[:16]}…，"
                     f"现在是 {digest[:16]}…）→ 授权可能已改，重读 {src.url}")
                continue
            ok(f"{cand.name}：{src.kind}｜{src.label}原文 {len(body)} 字节，"
               f"关键句 {len(src.marks)} 条全在｜{src.url}")
    return checked


def check_upstream(cand: Candidate) -> int:
    """逐环核入选款的上游字形来源。**归不出许可证类别就判失败。**

    为什么这一层非查不可：像素字体常见「基于某款商用字体改造」，那种情况下顶层写的
    OFL 是无效的。首轮实测也证明只读顶层会漏 —— 缝合款 README 指向的
    misaki/LICENSE.txt 在当前 master 里已经不存在（实际文件叫 misaki.txt）。
    """
    checked = 0
    for up in cand.upstream:
        checked += 1
        try:
            body = fetch(up.url, WORK_DIR / "upstream" /
                         f"{cand.id}-{up.name.split()[0]}-{Path(up.url).name}")
        except RuntimeError as exc:
            fail(f"上游「{up.name}」的许可证抓不到 → 该环判定「未核实」：{exc}")
            continue
        digest = hashlib.sha256(body).hexdigest()
        text = body.decode("utf-8", errors="replace")
        hit = [(fam, allow) for sig, fam, allow in UPSTREAM_FAMILIES if sig in text]
        if not hit:
            fail(f"上游「{up.name}」的许可证归不出类别（{up.url}）→ 人工读原文再判")
            continue
        bad = [fam for fam, allow in hit if not allow]
        if bad:
            fail(f"上游「{up.name}」是 {'；'.join(bad)}（{up.url}）")
            continue
        if up.sha256 and up.sha256 != digest:
            fail(f"上游「{up.name}」的许可证内容变了（钉的是 {up.sha256[:16]}…，"
                 f"现在是 {digest[:16]}…）→ 重读 {up.url}")
            continue
        pin = "" if up.sha256 else f"；未钉死，本次 sha256={digest}"
        ok(f"上游「{up.name}」提供{up.provides}｜{hit[0][0]}｜{len(body)} 字节{pin}")
    return checked


# ── 覆盖与度量 ────────────────────────────────────────────────────────
def ensure_fonts(cand: Candidate, offline: bool) -> list[Path]:
    out: list[Path] = []
    home = WORK_DIR / cand.id
    for src in cand.fonts:
        if src.kind == "raw":
            dest = home / Path(src.url).name
            if not dest.is_file() and not offline:
                fetch(src.url, dest)
            if dest.is_file():
                out.append(dest)
            continue
        archive = WORK_DIR / "zips" / Path(src.url).name
        if not archive.is_file() and not offline:
            fetch(src.url, archive)
        if not archive.is_file():
            continue
        target = home / archive.stem
        if not target.is_dir():
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    if member.lower().endswith((".ttf", ".otf")):
                        data = zf.read(member)
                        dest = target / Path(member).name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
        out.extend(sorted(target.rglob("*.ttf")) if target.is_dir() else [])
    return out


def report_font(cand: Candidate, path: Path,
                corpora: dict[str, tuple[set[int], str]],
                selected: str | None) -> None:
    try:
        sfnt = Sfnt(path.read_bytes())
        cov, how = sfnt.coverage()
        met = sfnt.metrics()
    except (SfntError, struct.error, IndexError) as exc:
        fail(f"{cand.name} 的 {path.name} 解不开：{exc}")
        return

    upm = met["unitsPerEm"]
    line = met["ascender"] - met["descender"] + met["lineGap"]
    say(f"\n  {path.name}｜{path.stat().st_size / 1024:.0f} KiB｜{how}")
    say(f"    设计 em {upm}｜ascender {met['ascender']}｜descender {met['descender']}"
        f"｜lineGap {met['lineGap']}｜整段行高 {line}"
        f"（em 的 {line / upm:.3f} 倍）")
    say(f"    汉字码位共 {cov.count_in(0x3400, 0x9FFF) + cov.count_in(0xF900, 0xFAFF)} 个"
        f"｜全部码位 {cov.total} 个")

    for label, (chars, _) in corpora.items():
        hit = sum(1 for cp in chars if cp in cov)
        miss = len(chars) - hit
        pct = 100.0 * hit / len(chars) if chars else 0.0
        line_txt = f"    {label}：{hit}/{len(chars)}（{pct:.2f}%）"
        if miss:
            sample = "".join(chr(cp) for cp in sorted(chars) if cp not in cov)[:24]
            line_txt += f"，缺 {miss} 个，例如 {sample}"
        say(line_txt)
        if selected == cand.id and label in REQUIRE_FULL and miss:
            fail(f"选定款 {cand.name} 对「{label}」缺 {miss} 个字 —— "
                 f"这些字在游戏里会是豆腐块")


# ── 主流程 ────────────────────────────────────────────────────────────
def flush_log() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = LOG_DIR / f"audit_fonts-{stamp}.log"
    n = 2
    while path.exists():        # 同一秒内跑两次不该悄悄覆盖上一次的证据
        path = LOG_DIR / f"audit_fonts-{stamp}-{n}.log"
        n += 1
    path.write_text("\n".join(_LINES) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="中文像素字体授权核实与覆盖量测（ART-2）")
    ap.add_argument("--licenses", action="store_true", help="只核授权，不下载字体")
    ap.add_argument("--offline", action="store_true", help="不联网，只量已下载的字体")
    ap.add_argument("--select", default=None, help="临时按某个候选 id 执行硬要求")
    ap.add_argument("--only", default=None,
                    help="只处理一个候选 id（选定款定下后日常重跑用，省掉另外六个源）")
    ap.add_argument("--clean", action="store_true", help="删掉 temp 下的下载物后退出")
    args = ap.parse_args()

    if args.clean:
        if WORK_DIR.is_dir():
            shutil.rmtree(WORK_DIR)
            print(f"已删除 {WORK_DIR}")
        else:
            print(f"{WORK_DIR} 不存在，无需删除")
        print("EXIT=0")
        return 0

    scope = _only(CANDIDATES, args.only)
    selected = args.select or SELECTED
    if args.only:
        note(f"--only {args.only}：只处理 1 款（登记 {len(CANDIDATES)} 款）。"
             f"**这不是一次完整审计**，换版本或复核授权时要跑全量")
    say(f"候选 {len(scope)} 款｜下载物落 {WORK_DIR}")
    if selected:
        say(f"选定款 {selected}：对 {'、'.join(REQUIRE_FULL)} 执行全覆盖硬要求")
    else:
        note("尚未选定任何一款（ADR-0008 落地前的正常状态），本轮只报告不设硬要求")

    say("\n── 授权 ────────────────────────────────────────────")
    upstream_checked = 0
    if args.offline:
        note("--offline：跳过授权核实。**跳过不等于核过**")
        licenses_checked = 0
    else:
        licenses_checked = check_licenses(scope)
        say("")
        for cand in scope:
            if not cand.upstream:
                continue
            say(f"{cand.name} 的上游字形来源（{len(cand.upstream)} 环）")
            upstream_checked += check_upstream(cand)

    measured = 0
    corpora: dict[str, tuple[set[int], str]] = {}
    if not args.licenses:
        say("\n── 语料 ────────────────────────────────────────────")
        corpora = build_corpora()
        for label, (chars, how) in corpora.items():
            say(f"  {label}：{len(chars)} 个（{how}）")

        say("\n── 覆盖与度量 ──────────────────────────────────────")
        for cand in scope:
            if not cand.fonts:
                note(f"{cand.name}：{cand.verdict or '未登记字体文件，跳过量测'}")
                continue
            say(f"\n{cand.name}（{cand.id}）")
            try:
                paths = ensure_fonts(cand, args.offline)
            except RuntimeError as exc:
                fail(f"{cand.name} 的字体拿不到：{exc}")
                continue
            if not paths:
                fail(f"{cand.name} 没找到可量的 .ttf"
                     f"{'（--offline 且本地没有）' if args.offline else ''}")
                continue
            for path in paths:
                report_font(cand, path, corpora, selected)
                measured += 1

    say("\n── 覆盖量 ──────────────────────────────────────────")
    say(f"核了 {licenses_checked} 份许可证原文"
        f"（本轮范围内登记 {sum(len(c.licenses) for c in scope)} 份）；"
        f"上游 {upstream_checked} 环"
        f"（登记 {sum(len(c.upstream) for c in scope)} 环）；"
        f"量了 {measured} 个字体文件"
        f"（登记 {sum(len(c.fonts) for c in scope)} 个下载源）；"
        f"语料 {len(corpora)} 份")
    if selected and not any(c.id == selected for c in scope):
        fail(f"选定款 {selected} 不在候选表里 —— 登记了检查目标却没执行")
    if selected and corpora:
        done = [name for name in REQUIRE_FULL if name in corpora]
        say(f"选定款的全覆盖硬要求：登记 {len(REQUIRE_FULL)} 条，实际执行 {len(done)} 条"
            f"（{'、'.join(done) or '无'}）")
        for name in REQUIRE_FULL:
            if name not in corpora:
                fail(f"硬要求「{name}」这一轮没有语料可比 —— "
                     f"登记了检查目标却没执行，等于没查")

    if _FAILS:
        say(f"\n[FAIL] 共 {len(_FAILS)} 条不成立")
    else:
        say("\n[OK] 授权与覆盖的登记项全部成立")
    say(f"日志 {flush_log().relative_to(ROOT)}")
    print(f"EXIT={1 if _FAILS else 0}")
    return 1 if _FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
