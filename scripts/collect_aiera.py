# -*- coding: utf-8 -*-
"""新智元采集器：WordPress REST API（https://aiera.com.cn/wp-json/wp/v2/posts）。

用法：
  python scripts/collect_aiera.py              # 增量；库为空时自动按 backfill_days 回填
  python scripts/collect_aiera.py --backfill   # 强制回填模式
  python scripts/collect_aiera.py --limit 2    # 最多处理 N 页（调试用）
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib


def load_sources() -> dict:
    return yaml.safe_load((lib.CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))


def fetch_posts(api: str, ua: str, per_page: int, page: int, retries: int) -> list:
    params = {
        "per_page": per_page, "page": page,
        "orderby": "date", "order": "desc",
        "_fields": "id,date,modified,link,title,content,excerpt,categories,tags",
    }
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(api, params=params, timeout=60, headers={"User-Agent": ua})
            if r.status_code == 400:  # WP：页码超出上限
                return []
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"aiera API 连续 {retries} 次失败：{last}")


def parse_post(p: dict) -> dict | None:
    pid = str(p.get("id") or "").strip()
    if not pid:
        return None
    title = lib.strip_html((p.get("title") or {}).get("rendered") or "")
    if not title:
        return None
    content_html = (p.get("content") or {}).get("rendered") or ""
    md_body = lib.html_to_md(content_html)
    excerpt = (lib.strip_html((p.get("excerpt") or {}).get("rendered") or "")[:300]
               or lib.md_to_plaintext(md_body, 300))
    link = lib.canonical_url(p.get("link") or f"https://aiera.com.cn/asi-post.html?id={pid}")
    pub = (p.get("date") or "")[:10]
    fulltext_rel = lib.write_fulltext(
        "aiera", pid,
        {"title": title, "source": "新智元", "url": link, "date": pub, "native_id": pid},
        md_body,
    )
    return {
        "uid": f"aiera:{pid}",
        "source": "aiera",
        "native_id": pid,
        "url": link,
        "title": title,
        "title_norm": lib.norm_title(title),
        "publish_date": pub,
        "content_md_path": fulltext_rel,
        "content_hash": lib.content_fingerprint(md_body),
        "content_chars": len(md_body),
        "status": "pending",
        "extra": {
            "excerpt": excerpt,
            "categories": p.get("categories"),
            "tags": p.get("tags"),
            "modified": p.get("modified"),
        },
    }


def collect(backfill: bool = False, limit_pages: int | None = None) -> dict:
    src = load_sources()
    cfg, pol = src["aiera"], src["politeness"]
    conn = lib.init_db()
    cutoff = (datetime.now(lib.CST) - timedelta(days=src["backfill_days"])).strftime("%Y-%m-%d")
    n_total = conn.execute("SELECT COUNT(*) FROM articles WHERE source='aiera'").fetchone()[0]
    do_backfill = backfill or n_total == 0
    max_pages = limit_pages or (cfg["backfill_max_pages"] if do_backfill else cfg["incremental_max_pages"])

    stats = {"source": "aiera", "mode": "backfill" if do_backfill else "incremental",
             "pages": 0, "fetched": 0, "inserted": 0, "exists": 0, "skipped_old": 0,
             "healthy": True, "errors": []}
    try:
        page = 1
        while page <= max_pages:
            posts = fetch_posts(cfg["api"], src["user_agent"], cfg["per_page"], page, pol["max_retries"])
            if not posts:
                break
            stats["pages"] += 1
            stats["fetched"] += len(posts)
            lib.dump_raw("aiera", posts, drop_fields=("content",))
            page_dates, page_inserted = [], 0
            for p in posts:
                pub = (p.get("date") or "")[:10]
                page_dates.append(pub)
                if do_backfill and pub and pub < cutoff:
                    stats["skipped_old"] += 1
                    continue
                art = parse_post(p)
                if art is None:
                    continue
                if lib.upsert_article(conn, art) == "inserted":
                    page_inserted += 1
                    stats["inserted"] += 1
                else:
                    stats["exists"] += 1
            conn.commit()
            oldest = min(d for d in page_dates if d) if page_dates else ""
            if do_backfill:
                if oldest and oldest < cutoff:
                    break
            elif page_inserted == 0:  # 整页无新文章，后面更旧
                break
            page += 1
            time.sleep(pol["aiera_delay_seconds"])
    except Exception as e:  # noqa: BLE001
        stats["healthy"] = False
        stats["errors"].append(str(e)[:500])
    lib.log_run(conn, "aiera", "collect", json.dumps(stats, ensure_ascii=False))
    conn.close()
    return stats


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="强制按 backfill_days 窗口回填")
    ap.add_argument("--limit", type=int, default=None, help="最多处理 N 页（调试）")
    args = ap.parse_args()
    stats = collect(backfill=args.backfill, limit_pages=args.limit)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
