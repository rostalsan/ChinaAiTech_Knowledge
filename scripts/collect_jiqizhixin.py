# -*- coding: utf-8 -*-
"""机器之心采集器（https://www.jiqizhixin.com）。

通道设计（2026-10 实测）：
  - 站方 WAF 对本机直连的详情页/API 已限流（仅列表接口放行）；
  - r.jina.ai 公共阅读器用其服务器代抓，实测可稳定取到「单篇 API 的 JSON 全文」；
  - 官方 sitemap 本机直连可用，负责全量 URL（slug+日期）发现。

  发现：jina → 列表 API（最新 20 篇，uuid/标题/预览），失败回落本机 Playwright；
        sitemap 直连 → 窗口期内全部 slug，缺 uuid 的条目先记 pending_content。
  全文：jina → /api/article_library/articles/{slug}（JSON，content 为 HTML）；
        slug 即稳定标识，uid = jqzx:<slug>。

用法：
  python scripts/collect_jiqizhixin.py               # 每日增量
  python scripts/collect_jiqizhixin.py --backfill    # 回填 sitemap 窗口 + 单批内容
  python scripts/collect_jiqizhixin.py --drain-all   # 持续补抓全部待补正文（初始回填用）
  python scripts/collect_jiqizhixin.py --limit 3     # 各通道限量（调试）
"""
import argparse
import gzip
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

JINA = "https://r.jina.ai/"


class JinaError(RuntimeError):
    pass


def load_sources() -> dict:
    return yaml.safe_load((lib.CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))


# ---------------- jina 代理 ----------------

def jina_get(path: str, retries: int = 3) -> str:
    url = JINA + "https://www.jiqizhixin.com" + path
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and "Markdown Content:" in r.text:
                return r.text
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
        except Exception as e:  # noqa: BLE001
            last = str(e)[:200]
        time.sleep(8 * (attempt + 1))
    raise JinaError(f"jina 抓取失败 {path}: {last}")


def jina_json(path: str) -> dict:
    text = jina_get(path)
    marker = text.find("Markdown Content:")
    i = text.find("{", marker + 1 if marker >= 0 else 0)
    if i < 0:
        raise JinaError(f"响应无 JSON：{path}")
    obj, _ = json.JSONDecoder().raw_decode(text[i:])
    return obj


# ---------------- 解析 ----------------

def parse_dt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), lib.CST).strftime("%Y-%m-%d")
    s = str(v).strip()
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s[:10]


def author_name(author) -> str:
    if isinstance(author, dict):
        return str(author.get("name") or author.get("nickname") or author.get("username") or "")
    return str(author or "")


# ---------------- 列表发现 ----------------

def fetch_list_via_jina(cfg: dict) -> list:
    data = jina_json(f"{cfg['library_api']}?page=1&per={cfg['per_page']}")
    items = data.get("articles") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise JinaError("列表接口返回结构异常")
    return items


def fetch_list_via_playwright(cfg: dict) -> list:
    """jina 不可用时的回落：本机浏览器内直接 fetch 列表 API。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        try:
            ctx = b.new_context(user_agent=cfg["user_agent"], locale="zh-CN",
                                viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.goto(cfg["base"] + cfg["articles_entry"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            data = page.evaluate(
                "async (u) => (await fetch(u, {credentials:'include'})).json()",
                f"{cfg['base']}{cfg['library_api']}?page=1&per={cfg['per_page']}",
            )
            return (data or {}).get("articles") or []
        finally:
            b.close()


def upsert_list_item(conn, it: dict) -> str:
    iid = str(it.get("id") or "")
    slug = str(it.get("slug") or "")
    key = slug or iid
    if not key:
        return "skip"
    title = lib.strip_html(it.get("title") or "")
    pub = parse_dt(it.get("publishedAt"))
    url = lib.canonical_url(f"https://www.jiqizhixin.com/articles/{key}")
    extra = {
        "slug": slug or None,
        "uuid": iid or None,
        "author": author_name(it.get("author")),
        "category": it.get("category"),
        "tags": it.get("tagList"),
        "cover": it.get("coverImageUrl"),
        "preview": lib.md_to_plaintext(str(it.get("content") or ""), 200),
    }
    row = conn.execute(
        "SELECT id, title, extra FROM articles WHERE source='jiqizhixin' AND uid=?",
        (f"jqzx:{key}",),
    ).fetchone()
    if row is not None:
        old = json.loads(row["extra"] or "{}")
        old.update(extra)
        conn.execute(
            "UPDATE articles SET title=?, title_norm=?, publish_date=COALESCE(NULLIF(publish_date,''),?), extra=? WHERE id=?",
            (title or row["title"], lib.norm_title(title), pub, json.dumps(old, ensure_ascii=False), row["id"]),
        )
        return "updated"
    conn.execute(
        """INSERT INTO articles
             (uid, source, native_id, url, title, title_norm, publish_date, fetched_at,
              content_md_path, content_hash, content_chars, status, extra)
           VALUES (?,?,?,?,?,?,?,?,NULL,'',0,'pending',?)""",
        (f"jqzx:{key}", "jiqizhixin", iid or None, url, title, lib.norm_title(title), pub,
         lib.now_str(), json.dumps(extra, ensure_ascii=False)),
    )
    return "inserted"


# ---------------- sitemap URL 兜底 ----------------

def sitemap_entries(cfg: dict, cutoff: str) -> list:
    r = requests.get(cfg["sitemap"], timeout=120, headers={"User-Agent": cfg["user_agent"]})
    r.raise_for_status()
    xml = gzip.decompress(r.content).decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r"<loc>(.*?)</loc>", xml, re.S):
        hit = lib._JQZX_URL_RE.search(m.group(1))
        if not hit:
            continue
        slug = hit.group(0).rsplit("/", 1)[-1]
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})", slug)
        if dm and dm.group(1) >= cutoff:
            out.append((slug, dm.group(1)))
    return out


def insert_sitemap_rows(conn, entries: list) -> int:
    n = 0
    for slug, date in entries:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE source='jiqizhixin' AND uid=?", (f"jqzx:{slug}",)
        ).fetchone()
        if row is not None:
            continue
        conn.execute(
            """INSERT INTO articles
                 (uid, source, native_id, url, title, title_norm, publish_date, fetched_at,
                  content_md_path, content_hash, content_chars, status, extra)
               VALUES (?,?,?,?,?,?,?,?,NULL,'',0,'pending_content',?)""",
            (f"jqzx:{slug}", "jiqizhixin", None,
             lib.canonical_url(f"https://www.jiqizhixin.com/articles/{slug}"),
             "", "", date, lib.now_str(),
             json.dumps({"slug": slug}, ensure_ascii=False)),
        )
        n += 1
    return n


def _remaining(conn) -> int:
    return conn.execute(
        """SELECT COUNT(*) FROM articles WHERE source='jiqizhixin'
           AND (content_md_path IS NULL OR content_md_path='') AND status != 'error'"""
    ).fetchone()[0]


# ---------------- 全文补抓 ----------------

def drain_content(conn, cap: int, delay: float, stats: dict) -> None:
    rows = conn.execute(
        """SELECT id, uid, url, title, publish_date, extra FROM articles
           WHERE source='jiqizhixin' AND (content_md_path IS NULL OR content_md_path='')
             AND status != 'error'
           ORDER BY publish_date DESC LIMIT ?""",
        (cap,),
    ).fetchall()
    consecutive_fail = 0
    for row in rows:
        extra = json.loads(row["extra"] or "{}")
        slug = extra.get("slug") or row["uid"].split(":", 1)[-1]
        time.sleep(delay + random.uniform(0, 1.2))
        try:
            j = jina_json(f"/api/article_library/articles/{slug}")
            consecutive_fail = 0
        except JinaError as e:
            stats["content_fail"] += 1
            consecutive_fail += 1
            stats["errors"].append(f"{slug}: {str(e)[:150]}")
            if consecutive_fail >= 3:
                stats["errors"].append("连续 3 次通道失败，中止本轮补抓")
                break
            continue
        title = lib.strip_html(str(j.get("title") or ""))
        content = str(j.get("content") or "")
        if not title and not content.strip():
            new_extra = dict(extra, error="empty_api")
            conn.execute("UPDATE articles SET status='error', extra=? WHERE id=?",
                         (json.dumps(new_extra, ensure_ascii=False), row["id"]))
            stats["content_fail"] += 1
            continue
        md = lib.html_to_md(content) if "<" in content else content.strip()
        pub = parse_dt(j.get("published_at")) or row["publish_date"]
        final_title = title or row["title"] or slug
        rel = lib.write_fulltext(
            "jiqizhixin", slug,
            {"title": final_title, "source": "机器之心", "url": row["url"], "date": pub,
             "native_id": extra.get("uuid") or "", "slug": slug,
             "author": extra.get("author") or author_name(j.get("author"))},
            md,
        )
        new_extra = dict(extra)
        new_extra["description"] = lib.strip_html(str(j.get("description") or ""))[:300]
        if j.get("cover_image_url"):
            new_extra["cover"] = j.get("cover_image_url")
        if j.get("author") and not extra.get("author"):
            new_extra["author"] = author_name(j.get("author"))
        conn.execute(
            """UPDATE articles SET title=?, title_norm=?, publish_date=COALESCE(NULLIF(?,''),publish_date),
                 content_md_path=?, content_hash=?, content_chars=?, status='pending', extra=? WHERE id=?""",
            (final_title, lib.norm_title(final_title), pub, rel,
             lib.content_fingerprint(md), len(md), json.dumps(new_extra, ensure_ascii=False), row["id"]),
        )
        conn.commit()  # 每篇即提交，避免长事务锁库（可与整理/构建并行）
        stats["content_ok"] += 1
    conn.commit()


# ---------------- 主流程 ----------------

def collect(backfill: bool = False, drain_all: bool = False, limit: int | None = None) -> dict:
    src = load_sources()
    cfg = src["jiqizhixin"]
    conn = lib.init_db()
    cutoff = (datetime.now(lib.CST) - timedelta(days=src["backfill_days"])).strftime("%Y-%m-%d")
    stats = {"source": "jiqizhixin", "mode": ("drain-all" if drain_all else "backfill" if backfill else "incremental"),
             "list_new": 0, "list_updated": 0, "sitemap_new": 0,
             "content_ok": 0, "content_fail": 0, "remaining": 0,
             "channels": {}, "errors": []}
    try:
        # 1) 列表发现
        items = []
        try:
            items = fetch_list_via_jina(cfg)
            stats["channels"]["list"] = "jina"
        except JinaError:
            try:
                items = fetch_list_via_playwright(cfg)
                stats["channels"]["list"] = "playwright"
            except Exception as e:  # noqa: BLE001
                stats["channels"]["list"] = f"failed({str(e)[:120]})"
                stats["errors"].append(f"列表通道失败：{str(e)[:200]}")
        if limit:
            items = items[:limit]
        for it in items:
            try:
                res = upsert_list_item(conn, it)
                if res == "inserted":
                    stats["list_new"] += 1
                elif res == "updated":
                    stats["list_updated"] += 1
            except Exception as e:  # noqa: BLE001
                stats["errors"].append(f"list item 解析失败：{str(e)[:150]}")
        conn.commit()

        # 2) sitemap 兜底发现
        try:
            entries = sitemap_entries(cfg, cutoff)
            if limit:
                entries = entries[:limit]
            stats["sitemap_new"] = insert_sitemap_rows(conn, entries)
            stats["channels"]["sitemap"] = f"ok(窗口内{len(entries)})"
            conn.commit()
        except Exception as e:  # noqa: BLE001
            stats["channels"]["sitemap"] = f"failed({str(e)[:120]})"
            stats["errors"].append(f"sitemap 失败：{str(e)[:200]}")

        # 3) 全文补抓
        if drain_all:
            cap = 10 ** 9
        else:
            cap = cfg["content_cap_backfill"] if backfill else cfg["content_cap_daily"]
        if limit:
            cap = min(cap, limit)
        drain_content(conn, cap, float(cfg["content_delay_seconds"]), stats)
        while drain_all:
            stats["remaining"] = _remaining(conn)
            if stats["remaining"] == 0 or stats["content_fail"] > 0:
                break
            drain_content(conn, cfg["content_cap_backfill"], float(cfg["content_delay_seconds"]), stats)
        stats["remaining"] = _remaining(conn)
    except Exception as e:  # noqa: BLE001
        stats["channels"]["fatal"] = str(e)[:200]
    lib.log_run(conn, "jiqizhixin", "collect", json.dumps({k: v for k, v in stats.items() if k != "errors"}, ensure_ascii=False))
    conn.close()
    return stats


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="回填 sitemap 窗口 + 单批内容")
    ap.add_argument("--drain-all", action="store_true", help="持续补抓全部待补正文（初始回填用）")
    ap.add_argument("--limit", type=int, default=None, help="各通道限量（调试）")
    args = ap.parse_args()
    stats = collect(backfill=args.backfill, drain_all=args.drain_all, limit=args.limit)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
