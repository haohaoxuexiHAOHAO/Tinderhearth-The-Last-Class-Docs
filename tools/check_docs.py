#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设计仓文档准出检查器。

为什么存在：WORKFLOW 的规则如果没有执行体，就只是散文，会随时间漂移。
本脚本把 WORKFLOW §3 / §4 / §6 与 ADR-0004 的可机检部分变成退出码。

用法（从设计仓根目录运行）：
    python tools/check_docs.py            # 全量检查，退出码 = FAIL 数量（上限 1）
    python tools/check_docs.py --report    # 只打规模趋势表，不判定
    python tools/check_docs.py --changed-only   # 只检查 git 里有改动的 md（给 hook 用）

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

    def fail(self, where: str, msg: str) -> None:
        self.fails.append(f"[FAIL] {where}：{msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"[WARN] {where}：{msg}")


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
    args = ap.parse_args()

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
    # 全库级检查始终看全量，否则「第二台账」「断号」「入口可达」根本查不出来
    check_single_ledger(all_docs, rep)
    check_issue_ids(all_docs, rep)
    check_reachable(all_docs, rep)

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
