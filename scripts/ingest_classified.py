# -*- coding: utf-8 -*-
"""合并 LLM 分类结果（data/queue/classified.jsonl）到主档，并重建 kb/。

「更新知识库」整理会话 SOP 第 4 步调用。幂等：uid 已 classified 的自动跳过，
除非该行带 "review": true（复核改判通道，对已分类条目执行 UPDATE 覆盖）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import build_kb
import dedup

QUEUE = lib.QUEUE_DIR / "classified.jsonl"
VALID_TYPES = {"news", "paper", "tutorial", "project", "opinion"}


def load_tree_ids() -> set:
    import yaml
    tree = yaml.safe_load((lib.CONFIG_DIR / "tree.yaml").read_text(encoding="utf-8"))
    return {n["id"] for n in tree.get("tree", [])}


def run(conn=None) -> dict:
    own = conn is None
    conn = conn or lib.init_db()
    stats = {"lines": 0, "ingested": 0, "reviewed": 0, "skipped_done": 0, "invalid": 0,
             "unknown_topics": [], "errors": []}
    if not QUEUE.exists():
        print(json.dumps(stats, ensure_ascii=False))
        return stats
    tree_ids = load_tree_ids()
    with QUEUE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["lines"] += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                stats["invalid"] += 1
                stats["errors"].append(f"JSON 解析失败：{str(e)[:80]}")
                continue
            uid = str(rec.get("uid") or "")
            if not uid:
                stats["invalid"] += 1
                continue
            row = conn.execute("SELECT status FROM articles WHERE uid=?", (uid,)).fetchone()
            if row is None:
                stats["invalid"] += 1
                stats["errors"].append(f"未知 uid：{uid}")
                continue
            review = rec.get("review") is True
            if row["status"] == "classified":
                if not review:
                    stats["skipped_done"] += 1
                    continue
                stats["reviewed"] += 1  # 复核改判：带 review 标记的重复 uid 走 UPDATE 覆盖
            item_type = rec.get("item_type")
            score = rec.get("value_score")
            topics = rec.get("topics")
            if item_type not in VALID_TYPES or not isinstance(score, int) or not 1 <= score <= 5 \
                    or not isinstance(topics, list) or not topics:
                stats["invalid"] += 1
                stats["errors"].append(f"字段不合法：{uid}")
                continue
            for t in topics:
                if isinstance(t, str) and t not in tree_ids and t not in stats["unknown_topics"] \
                        and not t.startswith("new:"):
                    stats["unknown_topics"].append(t)
            seed = rec.get("project_seed")
            conn.execute(
                """UPDATE articles SET item_type=?, value_score=?, takeaway=?, topics=?,
                     project_seed=?, status='classified' WHERE uid=?""",
                (item_type, score, str(rec.get("takeaway") or ""),
                 json.dumps([str(t) for t in topics], ensure_ascii=False),
                 json.dumps(seed, ensure_ascii=False) if seed else None, uid),
            )
            stats["ingested"] += 1
    conn.commit()
    if stats["ingested"]:
        dedup.run(conn)  # 新分类不改变指纹，这里主要是保持流程完整（幂等）
    build_kb.rebuild(conn)
    if own:
        conn.close()
    return stats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False, indent=1))
