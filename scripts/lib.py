# -*- coding: utf-8 -*-
"""公共库：路径、SQLite 主档、文本处理、指纹、全文落盘。所有脚本共用。"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FULLTEXT_DIR = DATA_DIR / "fulltext"
QUEUE_DIR = DATA_DIR / "queue"
KB_DIR = PROJECT_ROOT / "kb"
LEARNING_DIR = PROJECT_ROOT / "learning"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
DB_PATH = DATA_DIR / "kb.db"

CST = timezone(timedelta(hours=8))  # 两个信息源均为中国时区

_DIRS = (DATA_DIR, RAW_DIR, FULLTEXT_DIR, QUEUE_DIR, KB_DIR, LEARNING_DIR, REPORTS_DIR, LOGS_DIR)


def ensure_dirs() -> None:
    for d in _DIRS:
        d.mkdir(parents=True, exist_ok=True)


def now_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


# ---------------- SQLite 主档 ----------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT UNIQUE NOT NULL,
  source TEXT NOT NULL,
  native_id TEXT,
  url TEXT,
  title TEXT,
  title_norm TEXT,
  publish_date TEXT,
  fetched_at TEXT,
  content_md_path TEXT,
  content_hash TEXT,
  content_chars INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending',          -- pending|classified|pending_content|error
  item_type TEXT,                          -- news|paper|tutorial|project|opinion
  value_score INTEGER,
  takeaway TEXT,
  topics TEXT,                             -- JSON 数组：知识树节点 id
  project_seed TEXT,                       -- JSON 或 NULL
  dedup_group TEXT,
  github_urls TEXT,                        -- JSON 数组：正文中的 GitHub 仓库地址（硬筛选字段）
  app_tags TEXT,                           -- JSON 数组：应用分类标签（第二套知识脉络）
  extra TEXT                               -- JSON：excerpt/categories/cover 等
);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_pubdate ON articles(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_dedup ON articles(dedup_group);
CREATE TABLE IF NOT EXISTS events (
  dedup_group TEXT PRIMARY KEY,
  label TEXT,
  first_date TEXT,
  sources TEXT,                            -- JSON 数组
  member_count INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS run_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  source TEXT,
  action TEXT,
  detail TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> sqlite3.Connection:
    conn = get_conn()
    conn.executescript(SCHEMA)
    # 轻量迁移：老库补列
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "github_urls" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN github_urls TEXT")
    if "app_tags" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN app_tags TEXT")
    if "app_lock" not in cols:
        # 1 = 人工打标并锁定：机器打标循环与全量重算一律跳过（全量清空须 WHERE app_lock=0）
        conn.execute("ALTER TABLE articles ADD COLUMN app_lock INTEGER DEFAULT 0")
    conn.commit()
    return conn


# ---------------- 文本处理 ----------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\W_]+", re.UNICODE)
_IMG_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_MD_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_JQZX_URL_RE = re.compile(r"https?://www\.jiqizhixin\.com/articles/\d{4}-\d{2}-\d{2}(?:-\d+)?")
# GitHub 仓库链接硬筛选：owner/repo 级归一化（剥 .git / tree / blob / issues 等）
_GH_RE = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
_GH_TAIL_RE = re.compile(r"(\.git|/(?:tree|blob|issues|pull|releases|commits|wiki|actions|stargazers|forks).*)")


def extract_github_urls(text: str, limit: int = 8) -> list:
    """从正文提取 GitHub 仓库地址（owner/repo 归一化、去重）。无则返回 []。"""
    out = []
    for m in _GH_RE.finditer(text or ""):
        repo = _GH_TAIL_RE.sub("", m.group(1)).rstrip(".")
        if "/" not in repo:  # 只有 owner 没有仓库名（github.com/用户名）
            continue
        url = f"https://github.com/{repo}"
        if url not in out and repo.lower() not in ("sindresorhus/awesome",):
            out.append(url)
        if len(out) >= limit:
            break
    return out


def strip_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(text or ""))).strip()


def norm_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", strip_html(title))
    return _PUNCT_RE.sub("", t).lower()


def content_fingerprint(text: str) -> str:
    t = _WS_RE.sub("", unicodedata.normalize("NFKC", strip_html(text)))
    if not t:
        return ""
    return hashlib.md5(t[:20000].encode("utf-8")).hexdigest()


def canonical_url(url: str) -> str:
    if not url:
        return ""
    u = url.split("#", 1)[0].rstrip("/")
    if "?" in u:
        base, qs = u.split("?", 1)
        keep = [
            kv for kv in qs.split("&")
            if kv and not kv.split("=", 1)[0].lower().startswith(
                ("utm_", "spm", "sharer", "share_", "scene", "fr", "from"))
        ]
        u = base + ("?" + "&".join(keep) if keep else "")
    return u


def md_to_plaintext(md_text: str, limit: int = 2000) -> str:
    t = _IMG_MD_RE.sub(" ", md_text or "")
    t = _LINK_MD_RE.sub(r"\1", t)
    t = _WS_RE.sub(" ", t).strip()
    return t[:limit]


def html_to_md(html_text: str) -> str:
    if not html_text or not html_text.strip():
        return ""
    try:
        from bs4 import BeautifulSoup
        from markdownify import MarkdownConverter
    except ImportError:
        return strip_html(html_text)
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    converter = MarkdownConverter(heading_style="ATX", bullets="-")
    return converter.convert_soup(soup).strip()


# ---------------- 落盘 ----------------

def write_fulltext(source: str, filename: str, meta: dict, md_body: str) -> str:
    """写全文 markdown（带 frontmatter），返回相对项目根的路径（正斜杠）。"""
    ensure_dirs()
    d = FULLTEXT_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{filename}.md"
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    lines += ["---", "", md_body, ""]
    p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return p.relative_to(PROJECT_ROOT).as_posix()


def dump_raw(source: str, records: list, drop_fields: tuple = ()) -> None:
    """原始采集件按运行时间存 JSON（可指定剔除大字段，正文以 fulltext md 为准）。"""
    ensure_dirs()
    d = RAW_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    slim = [{k: v for k, v in r.items() if k not in drop_fields} for r in records]
    ts = datetime.now(CST).strftime("%Y-%m-%d_%H%M%S")
    p = d / f"{ts}.json"
    p.write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def log_run(conn: sqlite3.Connection, source: str, action: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO run_log (ts, source, action, detail) VALUES (?,?,?,?)",
        (now_str(), source, action, detail[:2000]),
    )
    conn.commit()


# ---------------- 主档写入 ----------------

def upsert_article(conn: sqlite3.Connection, a: dict) -> str:
    """按 uid 插入；已存在则跳过。返回 inserted|exists。"""
    row = conn.execute("SELECT id FROM articles WHERE uid=?", (a["uid"],)).fetchone()
    if row is not None:
        return "exists"
    conn.execute(
        """INSERT INTO articles
             (uid, source, native_id, url, title, title_norm, publish_date, fetched_at,
              content_md_path, content_hash, content_chars, status, extra)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            a["uid"], a["source"], a.get("native_id"), a.get("url"), a.get("title"),
            a.get("title_norm"), a.get("publish_date"), now_str(),
            a.get("content_md_path"), a.get("content_hash"), a.get("content_chars", 0),
            a.get("status", "pending"),
            json.dumps(a.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return "inserted"
