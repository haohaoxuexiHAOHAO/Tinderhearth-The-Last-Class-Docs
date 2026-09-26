#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设计仓文档准出检查器。

为什么存在：WORKFLOW 的规则如果没有执行体，就只是散文，会随时间漂移。
本脚本把 WORKFLOW §3 / §4 / §6 与 ADR-0004 的可机检部分变成退出码。

用法（从设计仓根目录运行）：
    python tools/check_docs.py            # 全量检查，退出码 = FAIL 数量（上限 1）
    python tools/check_docs.py --report    # 只打规模趋势表，不判定
    python tools/check_docs.py --fix-eol   # 只把行尾改回 .gitattributes 声明的样子

**没有任何东西会自动跑它。** 推送前钩子随 `ADR-0009` 删了，所以准出全靠人在
提交前自己跑一次；跑没跑过看不出来，这是那次决定明知并接受的代价。

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
    # 输出被重定向到文件或管道时，默认编码可能不是 UTF-8，打第一个中文就崩。
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
SYSTEM_SECTIONS = ("摘要", "术语", "上游约束", "结构", "接口", "边界与非目标", "理由与取舍", "验收", "下游同步")
DESIGN_SECTIONS = ("摘要", "背景与动机", "上游约束", "当前事实与证据", "设计",
                   "理由与取舍", "兼容性", "实现与过渡", "边界与非目标", "验收", "下游同步")
APPENDIX_PREFIX = "附录"

# ── 术语（ADR-0019）───────────────────────────────────────────────────
# 分家的判据是「这个词有几个家」：跨页共用的归共用表，只有一页在用的归那一页的
# 「术语」节，两处都有就是两个家。三条判定各挡一种会静默发生的错，见 `DOC-93`。
GLOSSARY_REL = "reference/术语表.md"
TERMS_SECTION = "术语"
# 共用表末尾那张「会撞」的表是交叉索引、不是定义 —— 同一个词在那里再出现一次是
# 应该的，所以取词条时切到它为止。判据那一份自己写着（「收词判据」一节）。
GLOSSARY_CROSS_INDEX = "## 这几个词会撞"
# 词条 = 表格行首那个加粗词：`| **X** | …`。两张表同一个形状。
TERM_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|", re.MULTILINE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)

# ── 图（templates/SYSTEM.md 的「什么时候该画图」）──────────────────────
# 图比散文更容易悄悄过期，因为看图的人不会逐条核对。两条判定：每张图旁有重画
# 条件、图里的标签在正文找得到。第二条把「图不许引入正文没有的事实」变成可判的。
MERMAID_OPEN_RE = re.compile(r"^\s*```\s*mermaid\s*$", re.IGNORECASE)
# 重画条件那一行的形状**写死在模板里**，这是它的可执行副本 —— 两处不许各写一个
# 样子。要求冒号后面有内容，否则空着一行也能过。
REDRAW_RE = re.compile(r"^\*\*重画条件\*\*：\S")
# 图型声明行（每个块的第一行），不是标签。
MERMAID_TYPE_RE = re.compile(
    r"^\s*(flowchart|graph|stateDiagram(-v2)?|sequenceDiagram|classDiagram"
    r"|erDiagram|gantt|journey|pie|mindmap|timeline|gitGraph|quadrantChart)\b",
    re.IGNORECASE)
# Mermaid 自己的关键字行：它们是记号，不是作者写的事实。
MERMAID_KEYWORD_RE = re.compile(
    r"^\s*(note\s+(right|left|over)\b|end\s+note\b|end\s*$|direction\b|classDef\b"
    r"|class\b|style\b|linkStyle\b|click\b|accTitle\b|accDescr\b|%%)",
    re.IGNORECASE)
# 连线的各种写法。切开它就得到两头的节点。**必须先切连线再找括号** ——
# 否则箭头那个 `>` 会被当成节点形状的开括号，把半行文字吞进标签里（踩过）。
MERMAID_ARROW_RE = re.compile(r"<?-{2,}[->ox]?|<?={2,}[=>]?|\.{2,}->?|--[ox]")
# 节点里的显示文字：`A["文字"]`、`B(文字)`、`C{文字}`、`D[[文字]]` 都算。
# 开括号里刻意不含 `>`：Mermaid 那个 `id>文字]` 的形状本库不用，而放它进来会与箭头打架。
MERMAID_BRACKET_RE = re.compile(r"[\[\(\{]{1,2}\s*\"?(.*?)\"?\s*[\]\)\}]{1,2}")
# 带显示文字的节点声明，连标识一起取：组 1 是标识、组 2 是显示文字。
MERMAID_NODE_RE = re.compile(
    r"([A-Za-z0-9_\u4e00-\u9fff]+)\s*[\[\(\{]{1,2}\s*\"?(.*?)\"?\s*[\]\)\}]{1,2}")
# 连线上的文字：`-->|文字|`。
MERMAID_PIPE_RE = re.compile(r"\|([^|]+)\|")

# ── 句长（FR-20）──────────────────────────────────────────────────────
# **上限的家就是下面这一行**，模板、PRD 与台账都只说「有上限」、不复述这个数。
# 它按实测分布定，定它的那一次见 `DOC-93` 的验证结果表。
# 它**按实测分布定，不是拍的**：线放在 P99 之上、长尾已经走平的那一段，再往下调
# 一档就要一次报出几十条。一条误报多的门禁会被绕过，而被绕过的门禁比没有门禁更坏。
# 定它那一次的分布由 `python tools/audit_readability.py` 打出来，**数字记在 `DOC-93`
# 的验证结果表里、不抄到这里** —— 抄过来就是一份会静默过期的历史数字。
SENTENCE_LIMIT = 150
SENTENCE_END = "。！？"
FENCE_LINE_RE = re.compile(r"^\s*```")

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


def collect() -> list[Doc]:
    """全库的 Markdown。**刻意没有「只看改动的」那一档** —— 它原来只给推送前钩子
    省时间用，而那个钩子随 `ADR-0009` 删了，留着就是一条没有调用者的分支。全量扫
    这个体量本来也只要几秒，而按改动清单裁剪会放走「你以为自己没碰过」的那类文件。
    """
    docs = []
    for p in all_markdown():
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8-sig")
        docs.append(Doc(path=p, text=text, meta=parse_front_matter(text) or {}))
    return docs


def git_managed_files() -> list[str] | None:
    """git 会管的文件：已跟踪 + 未被忽略的未跟踪。返回 None 表示问不出来。

    用 git 枚举而不是自己遍历目录，是为了让 `.gitignore` 自动生效 —— 否则
    `__pycache__/`、`.vs/` 之类的产物都会被拖进行尾检查。

    **`-z` 不是可选的。** `core.quotepath` 默认为 true，git 会把中文文件名转义成
    `\\344\\272\\272` 这种八进制；按原样拼路径会得到不存在的文件，于是**中文名文档被
    静默跳过**。本项目文档大半是中文名，那等于检查器假装工作。这个坑踩过一次。
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
        rep.fail(doc.rel, f"二级标题不符合骨架（{'SYSTEM' if want is SYSTEM_SECTIONS else 'DESIGN'} 模板）：\n"
                          f"        应为：{' / '.join(want)}\n"
                          f"        实为：{' / '.join(got) or '（没有二级标题）'}")
        return
    for extra in tail:
        if not extra.startswith(APPENDIX_PREFIX):
            rep.fail(doc.rel, f"骨架之后多了一节「{extra}」；"
                              f"末尾只允许以「{APPENDIX_PREFIX}」开头的小节")


def glossary_terms(text: str) -> list[str]:
    """共用表的词条。切到「会撞」那张表为止 —— 它是交叉索引，不是定义。"""
    cut = text.find(GLOSSARY_CROSS_INDEX)
    return TERM_ROW_RE.findall(text if cut < 0 else text[:cut])


def terms_section(text: str) -> tuple[str, list[str]]:
    """返回（「术语」那一节的正文, 它列的词条）。没有这一节就返回空。

    骨架守卫已经判过这一节存不存在与排在哪，所以这里只负责取内容。
    """
    m = re.search(rf"^##\s*{TERMS_SECTION}\s*$", text, re.MULTILINE)
    if not m:
        return "", []
    rest = text[m.end():]
    nxt = ANY_HEADING_RE.search(rest)
    body = rest if nxt is None else rest[: nxt.start()]
    return body, TERM_ROW_RE.findall(body)


def check_terms(docs: list[Doc], rep: Report) -> None:
    """术语三条（ADR-0019 的验证方法表）。

    各挡一种**过期时没有任何东西会报错**的错：抄一张与本页无关的表（词在表里、
    正文里没有）、一个词有两个家（共用表与某页术语节都写了它）、那张共用表只增
    不减地膨胀（词条没有任何系统文档在用）。

    共用表缺失或一个词条都解析不出来时判失败，不是跳过 —— 否则这三条会假装工作。
    """
    glossary = next((d for d in docs if d.rel == GLOSSARY_REL), None)
    if glossary is None:
        rep.fail(GLOSSARY_REL, "共用术语表缺失，术语三条判定这一轮**没有执行**（不是通过）")
        return
    shared = glossary_terms(glossary.text)
    if not shared:
        rep.fail(GLOSSARY_REL, "一个词条都没解析出来（词条 = 表格行首的加粗词），"
                               "说明词条解析坏了，这一轮**没有执行**")
        return

    systems = [d for d in docs if d.meta.get("type") in LONGLIVED_TYPES and not d.is_template]
    if not systems:
        rep.fail("术语守卫", f"一份 {sorted(LONGLIVED_TYPES)} 的文档都没检到，"
                            f"这一轮**没有执行**")
        return

    shared_set = set(shared)
    listed = 0
    for doc in systems:
        body, own = terms_section(doc.text)
        if not body:
            continue                       # 缺这一节由骨架守卫报
        elsewhere = doc.text.replace(body, "", 1)
        for t in own:
            listed += 1
            if t in shared_set:
                rep.fail(doc.rel, f"术语节里的「{t}」在[共用术语表]({GLOSSARY_REL})里也有 —— "
                                  f"一个词两个家。删掉本页这一行，或把它从共用表里删掉")
            if t not in elsewhere:
                rep.fail(doc.rel, f"术语节列了「{t}」，但本页正文里一次都没用到它 —— "
                                  f"抄一张与本页无关的表比没有表更误导")

    for t in shared:
        if not any(t in d.text for d in systems):
            rep.fail(GLOSSARY_REL, f"词条「{t}」没有任何系统文档在用 —— "
                                   f"删掉它，否则这张表只增不减地膨胀")
    rep.note(f"术语覆盖量：共用表 {len(shared)} 条词条／"
             f"{len(systems)} 份长期规格的术语节合计 {listed} 条")


def mermaid_blocks(text: str) -> list[tuple[int, list[str], str]]:
    """文档里的每张 Mermaid 图：(块首行号, 块内各行, 块后第一处非空行)。

    块后那一行拿来判重画条件。取「第一处非空行」而不是「紧邻下一行」，是因为
    Markdown 里图与说明之间照惯例空一行。
    """
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if not MERMAID_OPEN_RE.match(lines[i]):
            i += 1
            continue
        start = i
        i += 1
        body = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            body.append(lines[i])
            i += 1
        i += 1                              # 跳过收尾围栏
        after = next((lines[j].strip() for j in range(i, len(lines)) if lines[j].strip()), "")
        out.append((start + 1, body, after))
    return out


def mermaid_labels(body: list[str]) -> list[str]:
    """一张图里作者写下的标签文字，顺序去重。

    **只取节点上读者看得见的字**，外加 note 块里的正文。两样刻意不取：

    - **Mermaid 自己的记号**（图型声明、`[*]`、连线符号、`note`／`end` 这些关键字）
      不是作者写的事实。
    - **连线上的文字**（`-->|是|`、状态图 `: 超时` 那一段）。理由不是嫌麻烦：一条
      连线文字是**为这张图写的条件**，而它编码的那个事实 —— 这条流转存在 —— 已经
      由它连起来的两个节点承载了；而节点说的是「这个东西在本系统里存在」，那才是
      「图不许引入正文没有的事实」要挡的。实测还有一层：连线文字大半是 `是`／
      `没有`／`到了` 这类分支词，它们在正文里找得到也证明不了任何事。**连线文字的
      措辞因此归人读**（[ADR-0009](../decisions/ADR-0009-编辑器主导的开发模式.md) 的分工）。
    """
    # 先收一遍「标识 → 显示文字」：同一个节点后文常被裸引用（`本子 --> 解锁`），
    # 那处写的是标识、读者看到的仍是显示文字。不先收这一遍就会把标识当标签报。
    shown: dict[str, str] = {}
    for raw in body:
        for m in MERMAID_NODE_RE.finditer(raw):
            shown[m.group(1)] = m.group(2).strip()

    out: list[str] = []

    def add(s: str) -> None:
        s = shown.get(s.strip(), s).strip().strip('"').strip()
        # 纯记号与纯数字不算标签：它们在正文里找不到也说明不了任何事
        if s and s != "[*]" and not re.fullmatch(r"[\W\d_]+", s):
            if s not in out:
                out.append(s)

    for raw in body:
        line = raw.strip()
        if not line or MERMAID_TYPE_RE.match(line) or line.startswith("%%"):
            continue
        m = re.match(r"^note\s+(?:right|left|over)\s+of\s+(.+?)\s*$", line, re.IGNORECASE)
        if m:
            add(m.group(1))                 # note 挂在哪个节点上，那也是个标签
            continue
        if MERMAID_KEYWORD_RE.match(line):
            continue
        line = MERMAID_PIPE_RE.sub(" ", line)   # 连线文字不判，见上面的理由
        for seg in MERMAID_ARROW_RE.split(line):
            seg = seg.strip()
            if not seg:
                continue
            decls = list(MERMAID_NODE_RE.finditer(seg))
            if decls:
                # 有显示文字的节点：**只算显示文字**。标识（`本子` 之于
                # `本子["当事人那本"]`）是程序内名字，永远不渲染给读者，
                # 拿它去正文里找是凭构造就会失败的误报。
                for m in decls:
                    add(m.group(2))
                continue
            # 状态图把连线文字写在冒号后面：`A --> B: 条件`，冒号后那段不判
            head, _, _cond = seg.partition(":")
            add(head)                       # 裸节点（没有显示文字，标识就是渲染出来的字）
    return out


def prose_sentences(text: str) -> list[tuple[int, str]]:
    """正文段落里的句子，返回 (行号, 句子)。

    **不判的行**（FR-20 的误报面）：围栏块（含 Mermaid）、表格行、标题、引用块。
    表格行天生是长的（一格里一句话），代码与图不是给人读的散文，引用块是文首那段
    元信息。把它们算进来，这条判定的命中里绝大多数都不是「长句」。

    量之前先剥掉 Markdown 记号：链接只留显示文字（链接目标不是读者读的字，一条
    相对路径能凭空加四十个字符）、反引号与加粗只留里面的字、行首列表记号不算。
    **剥不干净的也写明**：行内 HTML 与脚注不剥，本库没有用它们。
    """
    out: list[tuple[int, str]] = []
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
        if FENCE_LINE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = raw.strip()
        if not s or s.startswith(("|", ">", "#", "---", "***")):
            continue
        s = MD_LINK_RE.sub(r"\1", s)          # [文字](目标) → 文字
        s = re.sub(r"`([^`]*)`", r"\1", s)    # `代码` → 代码
        s = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", s)
        s = LIST_ITEM_RE.sub("", s).strip()
        buf = ""
        for ch in s:
            buf += ch
            if ch in SENTENCE_END:
                if buf.strip():
                    out.append((i, buf.strip()))
                buf = ""
        if buf.strip():
            out.append((i, buf.strip()))
    return out


def check_sentence_length(doc: Doc, rep: Report) -> int:
    """正文段落里的单句不超过字数上限（FR-20）。

    上限那个数**只写在 `SENTENCE_LIMIT` 一处**，模板与 PRD 都不复述它。它是按实测
    分布定的，不是拍的：定它那一次用 `python tools/audit_readability.py` 只列不判地
    看全库分布，把线放在长尾的起点。**为什么不放在中位或 P90**：那样会一次报出几百
    条，而一条误报多的门禁会被绕过，被绕过的门禁比没有门禁更坏。这条挡的是「长句
    重新长回来」，所以它是棘轮 —— 不让最长的那一档再变长，不追求把全库拉到中位。

    **只判长期规格**（`type: system`／`model`），有两条理由而不是一条：① 那正是
    定上限时量过的那一群，把一个没量过的群体套上这个数，那个数就没有依据了；
    ② 冻结的体裁（归档件、已接受的 ADR）按规则不许用今天的说法改写，而正典这一轮
    明确不动 —— 对改不动的东西设门禁，只会逼人绕过它。别处的句长由人读时把握。

    返回量的句子数，供自报覆盖量用。
    """
    if doc.meta.get("type") not in LONGLIVED_TYPES or doc.is_template or doc.in_archive:
        return 0
    sentences = prose_sentences(doc.text)
    for line_no, s in sentences:
        if len(s) > SENTENCE_LIMIT:
            rep.fail(doc.rel, f"L{line_no} 单句 {len(s)} 字，超过上限 {SENTENCE_LIMIT} —— "
                              f"拆成两句（拆句不得改变这句话的结论）：\n"
                              f"        {s[:60]}…")
    return len(sentences)


def check_diagrams(doc: Doc, rep: Report) -> tuple[int, int]:
    """图两条：每张图旁有重画条件、图里的标签在本页找得到。

    为什么这两条值得各占一条判定：**图最主要的失效方式是静默腐烂** —— 流转改了
    而图没改，读者照着图走，而没有任何东西报错。重画条件那一行让「什么时候该重画」
    有个固定位置；标签核对让「图不许引入正文没有的事实」变成可判的。

    标签按**子串**比，所以「超时」对得上「超时自然站起」。返回（图数, 标签数）
    供自报覆盖量用。
    """
    if doc.is_template or doc.in_archive:
        return 0, 0
    blocks = mermaid_blocks(doc.text)
    if not blocks:
        return 0, 0
    # 干草堆 = 全文减掉所有 Mermaid 块。不减的话图里的标签总能在自己那一行找到，
    # 这条判定就永远为真。
    haystack = doc.text
    for _, body, _ in blocks:
        for line in body:
            haystack = haystack.replace(line, "")

    labels_seen = 0
    for line_no, body, after in blocks:
        if not REDRAW_RE.match(after):
            rep.fail(doc.rel, f"L{line_no} 这张 Mermaid 图旁没有重画条件那一行 —— "
                              f"形状固定为 `**重画条件**：<什么改动之后要重画>`"
                              f"（模板里那一行长什么样，守卫判的就是它）")
        for label in mermaid_labels(body):
            labels_seen += 1
            if label not in haystack:
                rep.fail(doc.rel, f"L{line_no} 那张图里的标签「{label}」"
                                  f"在本页正文与表里都找不到 —— "
                                  f"图是导航，不是第二份权威；要么正文补上这件事，"
                                  f"要么把标签改成正文里的说法")
    return len(blocks), labels_seen


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
    （踩坑记录 28）。单份 md 是低危，提交时索引会被规范化；**同一机制作用在可执行
    脚本上就是高危** —— 当时仓库里那个 `#!/bin/sh` 的推送前钩子被整份转成 CRLF
    之后，Git Bash 报 `bad interpreter: /bin/sh^M` 直接不执行，而**没有任何提示**。
    那个钩子随 `ADR-0009` 删了，但 `tools/` 下的 py 入口仍在这条策略的覆盖面里。

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
    ap.add_argument("--fix-eol", action="store_true",
                    help="把行尾改回 .gitattributes 声明的样子，不做其他检查")
    args = ap.parse_args()

    if args.fix_eol:
        return fix_line_endings()

    scope = all_docs = collect()
    if args.report:
        print_report(all_docs)
        return 0

    rep = Report()
    diagrams = labels = sentences = 0
    for doc in scope:
        check_front_matter(doc, rep)
        check_links(doc, rep)
        check_archive_boundary(doc, rep)
        check_genre_home(doc, rep)
        check_skeleton(doc, rep)
        check_ordinal_refs(doc, rep)
        check_self_count(doc, rep)
        check_code_paths(doc, rep)
        d, l = check_diagrams(doc, rep)
        diagrams += d
        labels += l
        sentences += check_sentence_length(doc, rep)
    rep.note(f"图覆盖量：检查 {diagrams} 张 Mermaid 图、{labels} 个标签")
    rep.note(f"句长覆盖量：量 {sentences} 句正文（上限 {SENTENCE_LIMIT} 字）")
    # 下面这几条按定义要看全量：「第二台账」「断号」「入口可达」「共用表里没人用
    # 的词条」都是全库级的事实，只看一部分文件根本查不出来。行尾也一样 —— 被静默
    # 转成 CRLF 的往往正是你以为自己没碰过的文件，而且它覆盖 md 之外的 py。
    check_single_ledger(all_docs, rep)
    check_issue_ids(all_docs, rep)
    check_reachable(all_docs, rep)
    check_section_refs(all_docs, rep)
    check_system_upstream(all_docs, rep)
    check_terms(all_docs, rep)
    check_code_repo_present(rep)
    check_line_endings(rep)

    for line in rep.warns:
        print(line)
    for line in rep.fails:
        print(line)

    scanned = len(scope)
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
