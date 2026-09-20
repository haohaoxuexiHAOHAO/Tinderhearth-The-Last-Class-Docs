#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设计仓文档准出检查器。

为什么存在：WORKFLOW 的规则如果没有执行体，就只是散文，会随时间漂移。
本脚本把 WORKFLOW §3 / §4 / §6 与 ADR-0004 的可机检部分变成退出码。

用法（从设计仓根目录运行）：
    python tools/check_docs.py            # 全量检查，退出码 = FAIL 数量（上限 1）
    python tools/check_docs.py --report    # 只打规模趋势表，不判定
    python tools/check_docs.py --changed-only   # 只检查 git 里有改动的 md（给 hook 用）
    python tools/check_docs.py --fix-eol   # 只把行尾改回 .gitattributes 声明的样子

输出约定（CONVENTIONS §17 的通用规则）：
    固定 UTF-8；每条问题打成 [FAIL] 或 [WARN]；末尾打一行 EXIT= 摘要。
    [FAIL] 必须修复；[WARN] 不阻断。

判什么：文件头、断链、归档边界、单一台账、编号引用得出来、入口可达、工作区行尾，
外加体裁归位与四条引用纪律（ADR-0010 与 WORKFLOW §3.5）—— 后面这些的共同点是
**它们过期时链接仍然有效**，所以非得专门判一次才查得出来。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    # 被 pre-push 或 hook 重定向调用时，默认编码可能不是 UTF-8，打第一个中文就崩。
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# 配额表（四档行数／字符数上限、台账逐格上限、豁免额度）随 ADR-0009 取消，
# 判定与常量一并删除。体量改为人工把握：`--report` 仍打规模趋势表供参考，但不再判定。
# 留着一个没有规则支撑的判定比没有判定更糟 —— 它某天报错时，没人查得到依据。

# ── 文件头允许值 ──────────────────────────────────────────────────────
REQUIRED_KEYS = ("type", "status", "owner", "last_verified")
# 没有 status 类型：动态状态不再单独成页，进度由 spec/ 下的 issue 勾选框承载。
VALID_TYPES = {
    "index", "governance", "backlog", "canon", "design", "system", "model",
    "adr", "template", "workdoc", "production", "reference", "archive",
}

# 长期规格有两个体裁，差别只在「它是什么」与因此该叫什么名字；位置、骨架、寿命都一样。
# 后缀写死，是为了把「数值模型不是一个系统」这件事变成可判定的，而不是一条白名单例外。
LONGLIVED_TYPES = {"system": "系统", "model": "模型"}

# ── 体裁归位（ADR-0010）────────────────────────────────────────────────
# 分家分的是寿命：系统文档是活的契约、提案是一次性论证。两者混在一个目录里时，
# 「设计稳定后上升进正典、本目录只留活跃部分」这条规则会对其中一种不成立。
SYSTEM_HOME = "design/"            # type: system 必须直接落在这里
PROPOSAL_HOME = "design/proposals/"  # type: design 必须落在这里

# 骨架（templates/SYSTEM.md 与 templates/DESIGN.md 是人读的权威源，这两行是它们的
# 可执行副本 —— 改模板的人要回来改这里，这是承认得起的一处重复：不复制就没有守卫）。
# 末尾允许追加以「附录」开头的小节，别的都不许多、不许少、不许换顺序。
SYSTEM_SECTIONS = ("摘要", "上游约束", "结构", "接口", "边界与非目标", "理由与取舍", "验收", "下游同步")
DESIGN_SECTIONS = ("摘要", "背景与动机", "上游约束", "当前事实与证据", "设计",
                   "理由与取舍", "兼容性", "实现与过渡", "边界与非目标", "验收", "下游同步")
APPENDIX_PREFIX = "附录"

# ── 引用纪律（WORKFLOW §3.5）──────────────────────────────────────────
# 为什么这三条要有守卫：它们过期时**链接仍然有效**，检查器原来查不出来。实测
# 99 处「文档 · 节名」引用里有 8 处指向已经不存在的节名；两处「第 N 步」在插入
# 新步骤后静默指错；反引号里 45 处代码路径有 4 处指向随 ADR-0009 删掉的文件。
SECTION_SEP = "·"
# 行首的加粗片段：`- **X**：…` 或 `**X**` 段首。本仓大量用它当小标题，所以它和
# 真标题一样算「节」—— 但仅限行首，不含正文里随手加粗的词。
BOLD_LEAD_RE = re.compile(r"^\s*(?:[-*]\s+)?\*\*(.+?)\*\*", re.MULTILINE)
ORDINAL_REF_RE = re.compile(r"第\s*\d+\s*步")
NUMBERED_LIST_RE = re.compile(r"^\s*1\.\s", re.MULTILINE)
# 自计数：行尾是冒号、行内最后一个计数词 ≥2、紧跟一段清单。取最后一个计数词是
# 因为「一个失败模式：」这类说法里的「一个」不是清单长度；只判 ≥2 同理。
SELF_COUNT_RE = re.compile(r"(两|三|四|五|六|七|八|九|十|\d+)\s*(条|项|步|类|处|份|个|节|种|块|层)")
CN_NUM = {"两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
LIST_ITEM_RE = re.compile(r"^(?:[-*]|\d+\.)\s")
# 反引号里看起来像仓库内文件的路径。两个仓都找，因为文档会同时引两边的工具。
CODE_PATH_RE = re.compile(
    r"`((?:rules|src|tests|tools|scenes|assets|config|data|content)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")
CODE_REPO = ROOT.parent / "Tinderhearth-The-Last-Class"
# 冻结的体裁不判引用纪律：归档件与已接受的 ADR 描述的是当时的事实，按规则不许
# 用今天的路径改写它们（WORKFLOW §4）。
FROZEN_PREFIXES = ("archive/", "decisions/", "templates/")
VALID_STATUS = {
    "active", "draft", "awaiting-answer", "approved", "in-progress",
    "testing", "awaiting-verify", "archived", "superseded",
    "accepted", "proposed", "rejected",
}
ARCHIVE_STATUS = {"archived", "superseded"}

# 归档边界用语（WORKFLOW §4）。单独出现“历史”二字不算边界。
ARCHIVE_BOUNDARY_WORDS = ("只读", "历史归档", "已废弃", "不得作为", "非依据")
# 引用 archive 时必须同行标注这个
CITE_ARCHIVE_MARK = "历史背景·非依据"
# 只对「会被当成现行依据」的文档类型强制上面的标注。
# WORKFLOW §4 的原文是「归档不得被正典/设计/制作/ADR 当作现行依据」——
# README、WORKFLOW、索引指向归档属于导航，不是拿它当依据，不该被拦。
CITE_ARCHIVE_ENFORCED_TYPES = {"canon", "design", "production", "adr"}

# 唯一待办台账（WORKFLOW §1）。也按相对路径索引。
LEDGER_REL = "spec/issues/README.md"

# 待办编号：正文里引用的编号必须在台账里定义得出来。
# 为什么需要这条：2026-08-26 实测发现 ADR-0005 引用 `ENG-1`、人物.md 引用 `NR-3`，
# 两个编号在台账里都不存在 —— 也就是「记账」这件事本身漏了账，而没有任何机制能发现。
ISSUE_ID_RE = re.compile(r"\b(?:GP|NR|UI|ART|ENG|DOC)-\d+\b")
LEDGER_ROW_ID_RE = re.compile(r"^\|\s*`((?:GP|NR|UI|ART|ENG|DOC)-\d+)`\s*\|", re.MULTILINE)

# ── 行尾（ENG-9）──────────────────────────────────────────────────────
# 策略本身不在这里复述：`.gitattributes` 是行尾策略的唯一权威源，在 Python 里再写
# 一份 glob 表就是第二处会漂移的说法。改了 `.gitattributes`，本检查自动跟着变。
#
# 二进制判定门槛，与 git 自己的做法一致：前若干字节内出现 NUL 就当二进制、不做行尾
# 规范化。这条不是可选的 —— 实测 `git check-attr eol -- x.png` 因为 `*` 通配也返回
# `lf`，没有二进制判定的话，仓库里加一张 PNG（文件头就含 `\r\n`）就会误报。
BINARY_SNIFF_BYTES = 8000

FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
# 组 1 是链接文字（节名引用要读它），组 2 是目标，组 3 是可选的锚点。
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s#]+)(#[^)\s]*)?\)")


@dataclass
class Doc:
    path: Path
    text: str
    meta: dict = field(default_factory=dict)

    @property
    def rel(self) -> str:
        return self.path.relative_to(ROOT).as_posix()

    @property
    def lines(self) -> int:
        return len(self.text.splitlines())

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def in_archive(self) -> bool:
        return self.rel.startswith("archive/")

    @property
    def is_template(self) -> bool:
        return self.rel.startswith("templates/")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []
        # 覆盖量自报行。不是问题，但必须打出来，否则看不出某条检查是不是在空转。
        self.notes: list[str] = []

    def fail(self, where: str, msg: str) -> None:
        self.fails.append(f"[FAIL] {where}：{msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"[WARN] {where}：{msg}")

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def parse_front_matter(text: str) -> dict | None:
    """极小的 YAML 文件头解析器：只支持 `key: value` 平铺，够用且零依赖。"""
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None
    meta: dict = {}
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def all_markdown() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md")
        if ".git" not in p.parts and "node_modules" not in p.parts
    )


def collect(changed_only: bool) -> list[Doc]:
    paths: list[Path] | None = None
    if changed_only:
        paths = git_changed_markdown()
        if paths is None:
            print("[WARN] 无法从 git 取改动清单，退回全量扫描")
            paths = all_markdown()
    if paths is None:
        paths = all_markdown()
    docs = []
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8-sig")
        docs.append(Doc(path=p, text=text, meta=parse_front_matter(text) or {}))
    return docs


def git_changed_markdown() -> list[Path] | None:
    """返回工作区里有改动（含未跟踪）的 md 路径。给 hook 省时间用。

    返回 None 表示「问不出来」（没装 git、不是仓库），调用方应退回全量扫描，
    而不是当成「没有改动」—— 静默跳过比慢一点坏得多。

    两个坑，都踩过：
    1. `core.quotepath` 默认为 true，git 会把中文文件名转义成 \\344\\272\\272 这种八进制。
       按原样拼路径会得到不存在的文件，于是**中文名文档被静默跳过**。
       本项目文档大半是中文名，那等于检查器假装工作。用 `-c core.quotepath=false` 关掉。
    2. 行尾用 `-z` 的 NUL 分隔，避免文件名里的空格或引号把字段切错。
    """
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status",
             "--porcelain", "--untracked-files=all", "-z"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout.decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None

    fields = [f for f in out.split("\0") if f]
    result, skip_next = [], False
    for field in fields:
        if skip_next:                      # 重命名的「原路径」紧跟在后面，跳过
            skip_next = False
            continue
        status, _, name = field[:2], field[2:3], field[3:]
        if status.startswith("R") or status.startswith("C"):
            skip_next = True               # -z 模式下 R/C 会多输出一个原路径字段
        if name.endswith(".md"):
            result.append(ROOT / name)
    return result


def git_managed_files() -> list[str] | None:
    """git 会管的文件：已跟踪 + 未被忽略的未跟踪。返回 None 表示问不出来。

    用 git 枚举而不是自己遍历目录，是为了让 `.gitignore` 自动生效 —— 否则
    `__pycache__/`、`.vs/` 之类的产物都会被拖进行尾检查。`-z` 分隔避免中文名被
    `core.quotepath` 转义成八进制（这个坑见 git_changed_markdown 的注释）。
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    seen: set[str] = set()
    result: list[str] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        name = raw.decode("utf-8", errors="replace")
        if name not in seen:          # 已跟踪与未跟踪两份清单可能有重复
            seen.add(name)
            result.append(name)
    return result


def git_eol_policy(paths: list[str]) -> dict[str, str] | None:
    """问 git 每个路径解析后的 `eol` 属性（`lf`／`crlf`／`unspecified`）。

    这是把 `.gitattributes` 当权威源的关键一步：规则解析交给 git，本脚本只负责
    比对实际字节。输出格式是 `<路径> NUL eol NUL <值> NUL` 三元组（已实测）。
    """
    if not paths:
        return {}
    payload = b"\0".join(p.encode("utf-8") for p in paths) + b"\0"
    try:
        out = subprocess.run(
            ["git", "check-attr", "-z", "--stdin", "eol"],
            cwd=ROOT, input=payload, capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    fields = out.split(b"\0")
    policy: dict[str, str] = {}
    for i in range(0, len(fields) - 2, 3):
        name = fields[i].decode("utf-8", errors="replace")
        policy[name] = fields[i + 2].decode("utf-8", errors="replace")
    return policy


def eol_targets() -> tuple[list[tuple[str, str, bytes]], int, int] | None:
    """收集有行尾要求的文本文件：[(相对路径, 期望行尾, 内容)]，外加两个跳过计数。

    返回 None 表示策略问不出来 —— 调用方必须判失败，不能当通过。
    """
    paths = git_managed_files()
    if paths is None:
        return None
    policy = git_eol_policy(paths)
    if policy is None:
        return None

    targets: list[tuple[str, str, bytes]] = []
    binary = unset = 0
    for rel in paths:
        want = policy.get(rel, "unspecified")
        if want not in ("lf", "crlf"):
            unset += 1
            continue
        try:
            with (ROOT / rel).open("rb") as fh:
                head = fh.read(BINARY_SNIFF_BYTES)
                if b"\0" in head:
                    binary += 1        # 二进制不做行尾规范化，也别整份读进来
                    continue
                data = head + fh.read()
        except OSError:
            continue                   # 已删除但还在索引里的路径，交给 git 自己报
        targets.append((rel, want, data))
    return targets, binary, unset


def count_eol_violations(want: str, data: bytes) -> tuple[int, int]:
    """按期望行尾数出违反处数：(不该有的 CRLF 或 LF, 不该有的单独 CR)。"""
    crlf = data.count(b"\r\n")
    lone_cr = data.count(b"\r") - crlf
    if want == "lf":
        return crlf, lone_cr
    return data.count(b"\n") - crlf, lone_cr


def check_front_matter(doc: Doc, rep: Report) -> None:
    if not doc.meta:
        rep.fail(doc.rel, "缺少 YAML 文件头（必须以 --- 包住的 type/status/owner/last_verified 开头）")
        return
    for key in REQUIRED_KEYS:
        if key not in doc.meta:
            rep.fail(doc.rel, f"文件头缺少必填字段 `{key}`")
    t, s = doc.meta.get("type"), doc.meta.get("status")
    if t and t not in VALID_TYPES:
        rep.fail(doc.rel, f"`type: {t}` 不在允许值内：{sorted(VALID_TYPES)}")
    if s and s not in VALID_STATUS:
        rep.fail(doc.rel, f"`status: {s}` 不在允许值内：{sorted(VALID_STATUS)}")
    d = doc.meta.get("last_verified", "")
    if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        rep.fail(doc.rel, f"`last_verified: {d}` 必须是 YYYY-MM-DD")
    if s == "superseded" and "superseded_by" not in doc.meta:
        rep.fail(doc.rel, "`status: superseded` 必须同时写 `superseded_by`")


def check_links(doc: Doc, rep: Report) -> None:
    for m in MD_LINK_RE.finditer(doc.text):
        target = m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = (doc.path.parent / target).resolve()
        if not resolved.exists():
            line_no = doc.text[: m.start()].count("\n") + 1
            rep.fail(doc.rel, f"L{line_no} 断链：`{target}`")


def check_archive_boundary(doc: Doc, rep: Report) -> None:
    """archive/ 下必须自证只读；现行文档引用 archive 必须同行标注。"""
    if doc.in_archive:
        if doc.meta.get("status") not in ARCHIVE_STATUS:
            # 目录索引是维护中的活文档，允许 active
            if not (doc.path.name == "README.md" and doc.meta.get("type") == "index"):
                rep.fail(doc.rel, f"archive/ 下的文档 status 必须是 {sorted(ARCHIVE_STATUS)} 之一")
        head = "\n".join(doc.text.splitlines()[:20])
        if not any(w in head for w in ARCHIVE_BOUNDARY_WORDS):
            rep.fail(doc.rel, f"归档件文首 20 行必须写明只读边界（{'/'.join(ARCHIVE_BOUNDARY_WORDS)}）")
        return
    if doc.is_template or doc.meta.get("type") not in CITE_ARCHIVE_ENFORCED_TYPES:
        return
    for i, line in enumerate(doc.text.splitlines(), 1):
        if re.search(r"\]\([^)]*archive/", line) and CITE_ARCHIVE_MARK not in line:
            rep.fail(doc.rel, f"L{i} 引用 archive/ 必须同行标注「{CITE_ARCHIVE_MARK}」")


def check_genre_home(doc: Doc, rep: Report) -> None:
    """体裁必须归位（ADR-0010）：系统文档在 `design/` 根，提案在 `design/proposals/`。

    不做这条判定的后果不是断链，而是**一个目录里混着两种寿命的文档** —— 于是
    「稳定后上升进正典、本目录只留活跃部分」这条规则对其中一种永远不成立，而没有
    任何机制能发现。
    """
    if doc.is_template or doc.in_archive:
        return
    t = doc.meta.get("type")
    if t in LONGLIVED_TYPES:
        head, _, tail = doc.rel.rpartition("/")
        if head + "/" != SYSTEM_HOME or "/" in tail:
            rep.fail(doc.rel, f"`type: {t}` 的长期规格必须直接放在 `{SYSTEM_HOME}` 下（见 ADR-0010）")
        suffix = LONGLIVED_TYPES[t]
        if not Path(doc.rel).stem.endswith(suffix):
            rep.fail(doc.rel, f"`type: {t}` 的文件名必须以「{suffix}」结尾 —— "
                              f"名字要说出它是什么；它若不是这一类，就换 `type`")
    elif t == "design":
        if not doc.rel.startswith(PROPOSAL_HOME):
            rep.fail(doc.rel, f"`type: design` 的提案必须放在 `{PROPOSAL_HOME}` 下；"
                              f"若它其实是某个系统的长期契约，改成 `type: system` 并移到 `{SYSTEM_HOME}`")


def check_skeleton(doc: Doc, rep: Report) -> None:
    """系统文档与提案各有固定骨架，不许多、不许少、不许换顺序（ADR-0010）。

    为什么要判顺序：骨架的价值在于「同一个问题总在同一个位置」—— 顺序一变，读者就得
    每份重新找一遍，而那正是「骨架随意」的样子。末尾可以追加「附录」小节。
    """
    if doc.is_template or doc.in_archive:
        return
    t = doc.meta.get("type")
    want = SYSTEM_SECTIONS if t in LONGLIVED_TYPES else DESIGN_SECTIONS if t == "design" else None
    if want is None:
        return
    got = [l[3:].strip() for l in doc.text.splitlines() if l.startswith("## ")]
    head, tail = got[: len(want)], got[len(want):]
    if tuple(head) != want:
        rep.fail(doc.rel, f"二级标题不符合骨架（{'SYSTEM' if t == 'system' else 'DESIGN'} 模板）：\n"
                          f"        应为：{' / '.join(want)}\n"
                          f"        实为：{' / '.join(got) or '（没有二级标题）'}")
        return
    for extra in tail:
        if not extra.startswith(APPENDIX_PREFIX):
            rep.fail(doc.rel, f"骨架之后多了一节「{extra}」；"
                              f"末尾只允许以「{APPENDIX_PREFIX}」开头的小节")


def section_anchors(text: str) -> list[str]:
    """一份文档里可以被「文档 · 节名」引用的名字：真标题 ＋ 行首加粗小标题。"""
    out = []
    for line in text.splitlines():
        if line.startswith("#"):
            out.append(line.lstrip("#").replace("**", "").replace("`", "").strip())
    for m in BOLD_LEAD_RE.finditer(text):
        out.append(m.group(1).replace("`", "").strip())
    return out


def check_section_refs(docs: list[Doc], rep: Report) -> None:
    """「文档 · 节名」里的节名必须在目标文件里找得到（WORKFLOW §3.5 第 ① 条）。

    这类引用过期时**链接仍然有效**，所以原来的断链检查查不出来：节被改名或删掉，
    读者点进去只会找不到那一节，而没有任何东西报错。
    """
    by_rel = {d.rel: d for d in docs}
    checked = 0
    for doc in docs:
        if doc.rel.startswith(FROZEN_PREFIXES):
            continue
        for m in MD_LINK_RE.finditer(doc.text):
            label = m.group(1).replace("**", "").replace("`", "").strip()
            target = m.group(2)
            if target.startswith(("http://", "https://", "mailto:")) or SECTION_SEP not in label:
                continue
            section = label.split(SECTION_SEP)[-1].strip()
            if not section:
                continue
            resolved = (doc.path.parent / target).resolve()
            try:
                rel = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            tgt = by_rel.get(rel)
            if tgt is None:
                continue                      # 断链由 check_links 报
            checked += 1
            if section == Path(rel).stem:      # 「分类 · 文档名」这种写法，不是节名
                continue
            if any(section in a for a in section_anchors(tgt.text)):
                continue
            line_no = doc.text[: m.start()].count("\n") + 1
            rep.fail(doc.rel, f"L{line_no} 节名引用失效：`{rel}` 里找不到「{section}」"
                              f"（改成目标文件真有的标题或加粗小标题）")
    rep.note(f"节名引用覆盖量：检查 {checked} 处「文档 {SECTION_SEP} 节名」")


def check_system_upstream(docs: list[Doc], rep: Report) -> None:
    """每份长期规格必须被至少一份正典链接到（ADR-0010）。

    没有正典上游的规格是孤岛 —— 它在替正典做决定，而权威层级说它不能。
    目标为空时判失败而不是跳过：一份都没有，说明体裁判定在空转。
    """
    systems = [d for d in docs if d.meta.get("type") in LONGLIVED_TYPES and not d.is_template]
    if not systems:
        rep.fail("长期规格上游守卫", f"一份 {sorted(LONGLIVED_TYPES)} 的文档都没检到，"
                                  f"这一轮**没有执行**")
        return
    cited: set[str] = set()
    for doc in docs:
        if not doc.rel.startswith("canon/"):
            continue
        for m in MD_LINK_RE.finditer(doc.text):
            target = m.group(2)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            try:
                cited.add((doc.path.parent / target).resolve().relative_to(ROOT).as_posix())
            except ValueError:
                continue
    for d in systems:
        if d.rel not in cited:
            rep.fail(d.rel, "没有任何正典链接到这份长期规格 —— 它缺上游，"
                            "要么正典该引用它，要么它写的东西不该放在这里")
    rep.note(f"长期规格上游覆盖量：{len(systems)} 份，全部要求有正典引用")


def check_ordinal_refs(doc: Doc, rep: Report) -> None:
    """不许按序号引用别处的编号清单（WORKFLOW §3.5 第 ② 条）。

    实测起因：每日结算的步序插进两步之后，另一份文档里「第 4、6、8 步」三处全部
    静默指错 —— 序号会随插步整体平移，而按步名写永远不会。
    """
    if doc.rel.startswith(FROZEN_PREFIXES) or doc.in_archive:
        return
    hits = ORDINAL_REF_RE.findall(doc.text)
    if not hits or NUMBERED_LIST_RE.search(doc.text):
        return                                 # 自己就有编号清单，视为引用自己的
    rep.fail(doc.rel, f"{len(hits)} 处按序号引用编号清单（{'、'.join(sorted(set(hits))[:3])}）；"
                      f"本文件自己没有编号清单，说明引的是别处的 —— 改成按步名引用")


def check_self_count(doc: Doc, rep: Report) -> None:
    """自计数要与紧随其后的清单一样长（WORKFLOW §3.5 第 ④ 条）。

    「三条」后面跟四条是加东西时最常见的过期形式。只判「行尾冒号 ＋ 行内最后一个
    计数词 ≥2 ＋ 紧跟清单」这一种形状，因为「一个失败模式：」这类说法里的数字不是
    清单长度 —— 收窄到这一形状之后，实测 81 份文档里两处命中都是真的。
    """
    if doc.rel.startswith(FROZEN_PREFIXES) or doc.in_archive:
        return
    lines = doc.text.splitlines()
    for i, line in enumerate(lines):
        if not line.rstrip().endswith(("：", ":")):
            continue
        ms = list(SELF_COUNT_RE.finditer(line))
        if not ms:
            continue
        raw = ms[-1].group(1)
        want = CN_NUM.get(raw) or (int(raw) if raw.isdigit() else 0)
        if want < 2 or want > 12:
            continue
        got = 0
        for s in lines[i + 1:]:
            if LIST_ITEM_RE.match(s):
                got += 1
            elif not s.strip() or s.startswith((" ", "\t")):
                continue          # 松散列表的空行、续行与嵌套项都不算新项，也不结束列表
            else:
                break             # 出现正文段落才算这份清单结束
        if got and got != want:
            rep.fail(doc.rel, f"L{i+1} 自计数与清单不符：写了「{raw}{ms[-1].group(2)}」，"
                              f"紧随的清单是 {got} 条（改数字，或干脆别写自计数）")


def check_code_paths(doc: Doc, rep: Report) -> None:
    """反引号里的仓内文件路径必须真的存在（WORKFLOW §3.5 第 ③ 条）。

    两个仓都找，因为文档会同时引设计仓的 `tools/` 与代码仓的 `rules/`。实测起因：
    随 `ADR-0009` 删掉的 `tools/check_scaling.py`、`tools/import_role_sheets.py` 与
    `tools/selfcheck_docs_guard.py` 在正典、踩坑记录与 README 里仍被写成现行执行体。
    """
    if doc.rel.startswith(FROZEN_PREFIXES) or doc.in_archive:
        return
    for m in CODE_PATH_RE.finditer(doc.text):
        p = m.group(1)
        if (ROOT / p).exists() or (CODE_REPO / p).exists():
            continue
        line_no = doc.text[: m.start()].count("\n") + 1
        rep.fail(doc.rel, f"L{line_no} 路径 `{p}` 在两个仓里都不存在"
                          f"（删掉这处引用，或改成真的落点）")


def check_code_repo_present(rep: Report) -> None:
    """代码仓不在预期位置时判失败，不静默跳过 —— 否则上面那条守卫会假装工作。"""
    if not CODE_REPO.is_dir():
        rep.fail("代码路径守卫", f"找不到代码仓 `{CODE_REPO.name}`（应与设计仓同级），"
                                f"这一轮路径检查**没有执行**（不是通过）")


def check_single_ledger(docs: list[Doc], rep: Report) -> None:
    """唯一待办台账（WORKFLOW §1）。

    这里替代了原先的 STATUS.md 结构检查。取消 STATUS.md 的理由见 ADR-0006：
    进度由 spec/ 下 issue 文件的验收勾选框承载，再单独维护一页动态状态就是第二个
    状态源。但「待办只有一处」这条必须留着守卫 —— 台账编号被正典、制作规格与
    归档三问跨文档引用，出现第二份台账会让那些引用指向不确定的地方。

    目标消失时静默放过等于守卫没执行，所以台账缺失判失败，不是跳过。
    """
    found = [d.rel for d in docs if d.meta.get("type") == "backlog" and not d.is_template]
    if LEDGER_REL not in found:
        rep.fail(LEDGER_REL, f"唯一待办台账缺失：必须存在 {LEDGER_REL} 且文件头为 `type: backlog`")
    for rel in found:
        if rel != LEDGER_REL:
            rep.fail(rel, f"出现第二个待办台账：`type: backlog` 只允许 {LEDGER_REL}")


def strip_fenced(text: str) -> str:
    """把围栏代码块的内容换成空行，保留行号。

    技能与模板里的示例编号（`ENG-5：……` 这种）写在围栏块里，不是真引用，
    不该被当成断号。用空行替换而不是删行，否则报出来的行号会偏。
    """
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def check_issue_ids(docs: list[Doc], rep: Report) -> None:
    """正文引用的待办编号必须在台账里定义（WORKFLOW §1）。

    编号是跨文档引用的稳定标识，正典、制作规格与归档三问都会引它。引用一个台账里
    没有的编号，等于把一件事记在了不存在的账上 —— 读者点不进去，而且那件事实际上
    没有人在跟。
    """
    ledger = next((d for d in docs if d.rel == LEDGER_REL), None)
    if ledger is None:
        return                      # check_single_ledger 已经报过缺失
    defined = set(LEDGER_ROW_ID_RE.findall(ledger.text))
    for doc in docs:
        if doc.in_archive or doc.rel == LEDGER_REL:
            continue
        body = strip_fenced(doc.text)
        seen = set()
        for m in ISSUE_ID_RE.finditer(body):
            got = m.group(0)
            if got in defined or got in seen:
                continue
            seen.add(got)
            line_no = body[: m.start()].count("\n") + 1
            rep.fail(doc.rel, f"L{line_no} 引用了台账里没有的编号 `{got}`"
                              f"（补进 {LEDGER_REL}，或改掉这处引用）")


def check_reachable(docs: list[Doc], rep: Report) -> None:
    """从 README.md 出发能否走到每份非归档文档（WORKFLOW §6 入口可达）。"""
    by_rel = {d.rel: d for d in docs}
    if "README.md" not in by_rel:
        rep.fail("README.md", "设计仓缺少唯一入口 README.md")
        return
    seen, queue = {"README.md"}, ["README.md"]
    while queue:
        cur = by_rel.get(queue.pop())
        if cur is None:
            continue
        for m in MD_LINK_RE.finditer(cur.text):
            target = m.group(2)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (cur.path.parent / target).resolve()
            try:
                rel = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            if rel.endswith(".md") and rel not in seen:
                seen.add(rel)
                queue.append(rel)
    for d in docs:
        if d.rel in seen or d.in_archive or d.rel == "README.md":
            continue
        rep.warn(d.rel, "从 README.md 无法经链接到达（接入文档地图，或确认它确实只是被引用的附件）")


def check_line_endings(rep: Report) -> None:
    r"""工作区行尾必须符合 `.gitattributes`（WORKFLOW §6，`ENG-9`）。

    为什么需要：`.gitattributes` 钉了 `* text=auto eol=lf`，却没有任何检查能发现
    工作区违反它 —— 有声明、无执行体。实测编辑工具把
    `reference/踩坑记录.md` 从 191 行纯 LF 整份转成 201 行全 CRLF，全程无提示
    （踩坑记录 28）。单份 md 是低危，提交时索引会被规范化；**同一机制作用在
    `.githooks/pre-push` 上就是高危** —— 那是 `#!/bin/sh` 脚本，带 `\r` 时
    Git Bash 报 `bad interpreter: /bin/sh^M` 直接不执行，**文档准出检查静默失效**。

    为什么不用 `git diff --check`：它对行尾只给 warning，退出码仍是 0，
    当不了门禁。而且它只看有 diff 的部分，未跟踪的新文件根本不进它的视野。

    两个方向都判：`eol=lf` 的文件里不许有 `\r`，`eol=crlf` 的（`*.bat`／`*.cmd`）
    里不许有裸 `\n`。只守一半等于只执行了半份 `.gitattributes`。
    """
    collected = eol_targets()
    if collected is None:
        rep.fail("行尾守卫", "问不出 git 的文件清单或 `eol` 属性，这一轮行尾守卫"
                            "**没有执行**（不是通过）—— 确认装了 git 且在仓库内运行")
        return
    targets, binary, unset = collected

    for rel, want, data in targets:
        bad_eol, lone_cr = count_eol_violations(want, data)
        if not bad_eol and not lone_cr:
            continue
        parts = []
        if bad_eol:
            parts.append(f"{bad_eol} 处 {'CRLF' if want == 'lf' else '单独的 LF'}")
        if lone_cr:
            parts.append(f"{lone_cr} 处单独的 CR")
        rep.fail(rel, f"行尾应为 {want.upper()}（`.gitattributes` 声明 eol={want}），"
                      f"实测有 {'、'.join(parts)}；"
                      f"跑 `python tools/check_docs.py --fix-eol` 改回来")

    # 自报覆盖量：一个文本文件都没检到就是空转。这种情况必须判失败 ——
    # 「跑过了、没报错」比守卫不存在更坏，因为它让人以为有护栏。
    if not targets:
        rep.fail("行尾守卫", "一个有行尾要求的文本文件都没检到，"
                            "说明文件清单或 `eol` 属性解析坏了")
    rep.note(f"行尾覆盖量：检查 {len(targets)} 个文本文件"
             f"（跳过 {binary} 个二进制、{unset} 个未声明 eol）")


def fix_line_endings() -> int:
    """把行尾改回 `.gitattributes` 声明的样子。

    为什么做成入口而不是每次现场写脚本：这件事已经发生过一次（`GP-1` 验收时用
    临时 Python 脚本修完就删），必然还会再发生。WORKFLOW §5 说会做第二次的操作
    要落成 `tools/` 下的入口。和检查共用同一套策略解析，两者不可能各说一套。
    """
    collected = eol_targets()
    if collected is None:
        print("[FAIL] 问不出 git 的文件清单或 `eol` 属性，没有改动任何文件")
        print("EXIT=1")
        return 1
    targets, binary, unset = collected

    fixed = 0
    for rel, want, data in targets:
        bad_eol, lone_cr = count_eol_violations(want, data)
        if not bad_eol and not lone_cr:
            continue
        normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if want == "crlf":
            normalized = normalized.replace(b"\n", b"\r\n")
        (ROOT / rel).write_bytes(normalized)
        print(f"[FIX] {rel}：{bad_eol + lone_cr} 处 → {want.upper()}")
        fixed += 1

    print(f"覆盖量：检查 {len(targets)} 个文本文件"
          f"（跳过 {binary} 个二进制、{unset} 个未声明 eol），改写 {fixed} 个")
    if fixed == 0:
        print("[OK] 行尾本来就是对的，没有改动任何文件")
    print("EXIT=0")
    return 0


def print_report(docs: list[Doc]) -> None:
    """规模趋势表，供人工判断体量，不判定 —— 配额随 ADR-0009 取消。"""
    print(f"{'文档':<52}{'行':>6}{'字符':>9}")
    print("-" * 70)
    for d in sorted(docs, key=lambda x: -x.lines):
        print(f"{d.rel:<52}{d.lines:>6}{d.chars:>9}")
    print("-" * 70)
    print(f"共 {len(docs)} 份，合计 {sum(d.lines for d in docs)} 行 / {sum(d.chars for d in docs)} 字符")


def main() -> int:
    ap = argparse.ArgumentParser(description="设计仓文档准出检查")
    ap.add_argument("--report", action="store_true", help="只打规模趋势表，不判定")
    ap.add_argument("--changed-only", action="store_true", help="只检查有改动的 md（给 hook 用）")
    ap.add_argument("--fix-eol", action="store_true",
                    help="把行尾改回 .gitattributes 声明的样子，不做其他检查")
    args = ap.parse_args()

    if args.fix_eol:
        return fix_line_endings()

    all_docs = collect(changed_only=False)
    if args.report:
        print_report(all_docs)
        return 0

    scope = collect(changed_only=True) if args.changed_only else all_docs
    if args.changed_only and not scope:
        print("[OK] 没有改动的 Markdown，跳过检查")
        print("EXIT=0")
        return 0

    rep = Report()
    for doc in scope:
        check_front_matter(doc, rep)
        check_links(doc, rep)
        check_archive_boundary(doc, rep)
        check_genre_home(doc, rep)
        check_skeleton(doc, rep)
        check_ordinal_refs(doc, rep)
        check_self_count(doc, rep)
        check_code_paths(doc, rep)
    # 全库级检查始终看全量，否则「第二台账」「断号」「入口可达」根本查不出来。
    # 行尾也在这一档：被静默转成 CRLF 的往往正是你以为自己没碰过的文件，
    # 而且它覆盖 md 之外的 sh 与 py —— 按改动清单裁剪等于放走高危的那一类。
    check_single_ledger(all_docs, rep)
    check_issue_ids(all_docs, rep)
    check_reachable(all_docs, rep)
    check_section_refs(all_docs, rep)
    check_system_upstream(all_docs, rep)
    check_code_repo_present(rep)
    check_line_endings(rep)

    for line in rep.warns:
        print(line)
    for line in rep.fails:
        print(line)

    # 自报覆盖量：--changed-only 模式下若漏扫（例如文件名转义导致路径解析失败），
    # 必须能看出来，否则检查器会假装工作。这个坑真踩过一次。
    scanned = len(scope)
    if args.changed_only:
        missing = sorted(set(d.rel for d in scope) - set(d.rel for d in all_docs))
        if missing:
            print(f"[FAIL] 改动清单里有 {len(missing)} 个路径不在全库扫描结果中，"
                  f"说明路径解析有问题：{missing[:5]}")
            rep.fails.append("覆盖量自检失败")
        print(f"覆盖量：改动 {scanned} 份 / 全库 {len(all_docs)} 份")
    for line in rep.notes:
        print(line)

    print(f"\n结果：扫描 {scanned} 份文档（全库 {len(all_docs)} 份）"
          f"／{len(rep.fails)} 项必须修复／{len(rep.warns)} 条提示")
    if rep.fails:
        print("EXIT=1")
        return 1
    print("[OK] 无必须修复项")
    print("EXIT=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
