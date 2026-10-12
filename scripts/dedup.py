# -*- coding: utf-8 -*-
"""去重与跨源同事件分组。

三层判定（针对 dedup_group 为空的文章，按发布日升序处理）：
  1. 内容指纹一致（同文转载/重发）
  2. 规范化 URL 一致
  3. 标题归一化后相同，或 rapidfuzz 相似度 >= 阈值 且发布日相差 <= 窗口
     （机器之心 vs 新智元 常报道同一事件：全部保留，只打同组标记）

分组成员都保留；组信息写入 events 表（label 取组内最早一篇的标题）。
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

from rapidfuzz import fuzz

TITLE_RATIO = 88     # 标题相似度阈值
WINDOW_DAYS = 14     # 同事件时间窗口


def _days(a: str, b: str) -> int | None:
    try:
        da = datetime.strptime(a[:10], "%Y-%m-%d")
        db = datetime.strptime(b[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return (db - da).days


def _gid(title_norm: str, first_date: str) -> str:
    return "g" + hashlib.md5((title_norm + "|" + first_date).encode("utf-8")).hexdigest()[:12]


def run(conn=None) -> dict:
    own = conn is None
    conn = conn or lib.init_db()

    groups: list[dict] = []
    by_gid: dict[str, dict] = {}
    by_hash: dict[str, dict] = {}
    by_url: dict[str, dict] = {}

    # 预载已有分组（新文章可与之归并）
    for row in conn.execute(
        """SELECT dedup_group, MIN(publish_date) AS fd FROM articles
           WHERE dedup_group IS NOT NULL GROUP BY dedup_group"""
    ):
        g = {"gid": row["dedup_group"], "first_date": row["fd"] or "", "members": [],
             "label": None, "sources": set(), "existing": True, "touched": False,
             "new_members": 0}
        groups.append(g)
        by_gid[g["gid"]] = g
    for row in conn.execute(
        """SELECT dedup_group, title_norm, publish_date FROM articles
           WHERE dedup_group IS NOT NULL AND title_norm != ''"""
    ):
        g = by_gid.get(row["dedup_group"])
        if g is not None:
            g["members"].append({"id": None, "tn": row["title_norm"], "date": row["publish_date"] or ""})
    for row in conn.execute(
        """SELECT dedup_group, content_hash, url FROM articles
           WHERE dedup_group IS NOT NULL AND (content_hash != '' OR url IS NOT NULL)"""
    ):
        g = by_gid.get(row["dedup_group"])
        if g is None:
            continue
        if row["content_hash"]:
            by_hash.setdefault(row["content_hash"], g)
        cu = lib.canonical_url(row["url"] or "")
        if cu:
            by_url.setdefault(cu, g)

    stats = {"processed": 0, "groups_new": 0, "merged_into_existing": 0, "merged_new": 0, "singleton": 0}

    rows = conn.execute(
        """SELECT id, uid, source, title, title_norm, publish_date, url, content_hash
           FROM articles WHERE dedup_group IS NULL AND title_norm != ''
           ORDER BY publish_date, id"""
    ).fetchall()

    for r in rows:
        stats["processed"] += 1
        date = r["publish_date"] or ""
        tn = r["title_norm"] or ""
        ch = r["content_hash"] or ""
        cu = lib.canonical_url(r["url"] or "")
        target = None
        if ch and ch in by_hash:
            target = by_hash[ch]
        elif cu and cu in by_url:
            target = by_url[cu]
        if target is None and tn:
            for g in groups:
                dd = _days(g["first_date"], date)
                if dd is None or dd < 0 or dd > WINDOW_DAYS:
                    continue
                best = max((fuzz.token_sort_ratio(tn, m["tn"]) for m in g["members"] if m["tn"]), default=0)
                if best >= TITLE_RATIO:
                    target = g
                    break

        if target is None:
            gid = _gid(tn or r["uid"], date or "unknown")
            target = {"gid": gid, "first_date": date, "members": [], "label": r["title"] or r["uid"],
                      "sources": {r["source"]}, "existing": False, "touched": True, "new_members": 1}
            groups.append(target)
            by_gid[gid] = target
            stats["groups_new"] += 1
            stats["singleton"] += 1
        else:
            target["touched"] = True
            target["new_members"] += 1
            target["sources"].add(r["source"])
            if target["existing"]:
                stats["merged_into_existing"] += 1
            else:
                stats["merged_new"] += 1
                stats["singleton"] -= 1

        target["members"].append({"id": r["id"], "tn": tn, "date": date})
        if ch:
            by_hash.setdefault(ch, target)
        if cu:
            by_url.setdefault(cu, target)
        conn.execute("UPDATE articles SET dedup_group=? WHERE id=?", (target["gid"], r["id"]))

    conn.commit()

    for g in groups:
        if not g["touched"]:
            continue
        n = conn.execute("SELECT COUNT(*) FROM articles WHERE dedup_group=?", (g["gid"],)).fetchone()[0]
        sources = [s for (s,) in conn.execute(
            "SELECT DISTINCT source FROM articles WHERE dedup_group=?", (g["gid"],))]
        if g["existing"]:
            conn.execute(
                "UPDATE events SET member_count=?, sources=?, updated_at=? WHERE dedup_group=?",
                (n, json.dumps(sources), lib.now_str(), g["gid"]),
            )
        else:
            conn.execute(
                """INSERT INTO events (dedup_group, label, first_date, sources, member_count, updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(dedup_group) DO UPDATE SET member_count=excluded.member_count,
                     sources=excluded.sources, updated_at=excluded.updated_at""",
                (g["gid"], g["label"], g["first_date"], json.dumps(sources), n, lib.now_str()),
            )
    conn.commit()

    if own:
        conn.close()
    return stats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False))
