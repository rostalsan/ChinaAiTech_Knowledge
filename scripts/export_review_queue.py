# -*- coding: utf-8 -*-
"""导出待 LLM 复核的【规则·带仓库】兜底条目为复核队列。

用法：python scripts/export_review_queue.py

这些条目由 bulk_news.py 规则兜底产生（takeaway 带【规则·带仓库】前缀，机械判
project/3 分），未经 LLM 逐篇判定。本脚本把它们导出为 data/queue/review_github.jsonl，
字段与 pending.jsonl 对齐（uid/title/text/github），另带 current 当前判定供对照。

LLM 复核后按 config/classify.md 判定，带 "review": true 追加写 data/queue/classified.jsonl；
ingest_classified.py 对已 classified 的 uid 仅在 review=true 时改判（UPDATE 覆盖）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import build_kb

OUT = lib.QUEUE_DIR / "review_github.jsonl"


def run() -> dict:
    conn = lib.init_db()
    rows = conn.execute(
        """SELECT * FROM articles
           WHERE status='classified' AND takeaway LIKE '【规则·带仓库】%'
           ORDER BY publish_date DESC, id DESC""").fetchall()
    lib.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            body = build_kb.read_fulltext_body(r["content_md_path"]) if r["content_md_path"] else ""
            extra = json.loads(r["extra"] or "{}")
            rec = {
                "uid": r["uid"], "source": r["source"],
                "title": r["title"], "publish_date": r["publish_date"], "url": r["url"],
                "github": json.loads(r["github_urls"] or "[]"),
                "current": {"item_type": r["item_type"], "value_score": r["value_score"],
                            "topics": json.loads(r["topics"] or "[]")},
                "excerpt": (extra.get("excerpt") or lib.md_to_plaintext(body, 300) or ""),
                "text": lib.md_to_plaintext(body, 2000),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    conn.close()
    return {"exported": n, "out": str(OUT.relative_to(lib.PROJECT_ROOT))}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False))
