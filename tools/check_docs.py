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
    [FAIL] 必须修复；[WARN] 是软上限提醒，不阻断。
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

# ── 配额表（WORKFLOW §3）──────────────────────────────────────────────
# (行软, 行硬, 字符软, 字符硬)
QUOTA_DEFAULT = (600, 900, 40_000, 60_000)
# 按仓库相对路径索引，不按文件名 —— 台账叫 README.md，按文件名会命中每一份 README。
QUOTA_BY_REL = {
    "WORKFLOW.md": (150, 200, 12_000, 16_000),
    "spec/issues/README.md": (200, 250, 20_000, 25_000),
}
# spec/ 下的 PRD、SPEC 与 issue 文件
QUOTA_SPEC = (250, 350, 20_000, 28_000)

# ── 文件头允许值（WORKFLOW §3）────────────────────────────────────────
REQUIRED_KEYS = ("type", "status", "owner", "last_verified")
# 没有 status 类型：动态状态不再单独成页，进度由 spec/ 下的 issue 勾选框承载。
VALID_TYPES = {
    "index", "governance", "backlog", "canon", "design",
    "adr", "template", "workdoc", "production", "reference", "archive",
}
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

# 台账逐格限制（WORKFLOW §3）
CELL_LIMITS = {
    LEDGER_REL: 360,
    "archive/history/变更日志归档.md": 220,
}

# ── 行尾（ENG-9）──────────────────────────────────────────────────────
# 策略本身不在这里复述：`.gitattributes` 是行尾策略的唯一权威源，在 Python 里再写
# 一份 glob 表就是第二处会漂移的说法。改了 `.gitattributes`，本检查自动跟着变。
#
# 二进制判定门槛，与 git 自己的做法一致：前若干字节内出现 NUL 就当二进制、不做行尾
# 规范化。这条不是可选的 —— 实测 `git check-attr eol -- x.png` 因为 `*` 通配也返回
# `lf`，没有二进制判定的话，仓库里加一张 PNG（文件头就含 `\r\n`）就会误报。
BINARY_SNIFF_BYTES = 8000

FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s#]+)(#[^)\s]*)?\)")


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


def quota_for(doc: Doc) -> tuple[int, int, int, int]:
    if doc.rel in QUOTA_BY_REL:
        return QUOTA_BY_REL[doc.rel]
    if doc.rel.startswith("spec/") and doc.meta.get("type") == "workdoc":
        return QUOTA_SPEC
    return QUOTA_DEFAULT


def effective_size(doc: Doc) -> tuple[int, int]:
    """工作文档的「待确认问题」一节不计入配额（WORKFLOW §3）。"""
    if doc.meta.get("type") != "workdoc":
        return doc.lines, doc.chars
    kept, skipping = [], False
    for line in doc.text.splitlines():
        if re.match(r"^#{2,3}\s", line):
            skipping = "待确认问题" in line
        if not skipping:
            kept.append(line)
    body = "\n".join(kept)
    return len(kept), len(body)


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


def check_quota(doc: Doc, rep: Report) -> None:
    if "quota_exempt" in doc.meta:
        return
    ls, lh, cs, ch = quota_for(doc)
    lines, chars = effective_size(doc)
    if lines > lh:
        rep.fail(doc.rel, f"行数 {lines} 超过硬上限 {lh}（按主题或职责拆分，或在文件头写 quota_exempt 理由）")
    elif lines > ls:
        rep.warn(doc.rel, f"行数 {lines} 超过软上限 {ls}")
    if chars > ch:
        rep.fail(doc.rel, f"字符数 {chars} 超过硬上限 {ch}")
    elif chars > cs:
        rep.warn(doc.rel, f"字符数 {chars} 超过软上限 {cs}")


def check_links(doc: Doc, rep: Report) -> None:
    for m in MD_LINK_RE.finditer(doc.text):
        target = m.group(1)
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


def check_cells(doc: Doc, rep: Report) -> None:
    limit = CELL_LIMITS.get(doc.rel)
    if limit is None:
        return
    for i, line in enumerate(doc.text.splitlines(), 1):
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        if re.fullmatch(r"\|[\s\-:|]+\|", s):     # 分隔行
            continue
        for cell in s.strip("|").split("|"):
            if len(cell.strip()) > limit:
                rep.fail(doc.rel, f"L{i} 单元格 {len(cell.strip())} 字符，超过 {limit}（把解释移回该行链接的正文）")
                break


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
            target = m.group(1)
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
    工作区违反它 —— 有声明、无执行体。2026-08-29 实测编辑工具把
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
    print(f"{'文档':<52}{'行':>6}{'字符':>9}  配额")
    print("-" * 88)
    for d in sorted(docs, key=lambda x: -x.lines):
        ls, lh, cs, ch = quota_for(d)
        lines, chars = effective_size(d)
        flag = "FAIL" if lines > lh or chars > ch else ("WARN" if lines > ls or chars > cs else "ok")
        print(f"{d.rel:<52}{lines:>6}{chars:>9}  {ls}/{lh} 行 · {cs}/{ch} 字符  [{flag}]")
    print("-" * 88)
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
        check_quota(doc, rep)
        check_links(doc, rep)
        check_archive_boundary(doc, rep)
        check_cells(doc, rep)
    # 全库级检查始终看全量，否则「第二台账」「断号」「入口可达」根本查不出来。
    # 行尾也在这一档：被静默转成 CRLF 的往往正是你以为自己没碰过的文件，
    # 而且它覆盖 md 之外的 sh 与 py —— 按改动清单裁剪等于放走高危的那一类。
    check_single_ledger(all_docs, rep)
    check_issue_ids(all_docs, rep)
    check_reachable(all_docs, rep)
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
