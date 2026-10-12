# -*- coding: utf-8 -*-
"""把主档导出为 Web 前后端使用的 JSON 数据（web/server/data/*.json）。

由 build_kb.rebuild() 在每次重建后自动调用；也可手动运行：
  python scripts/export_web.py

导出内容：
  overview.json  统计概览
  articles.json  全部已分类文章的扁平数组（前端三套视图共用）
  topics.json    主题知识树（阶段+节点，来自 tree.yaml 与主档 topics）
  apptree.json   应用分类体系（来自 app-tree.yaml 与主档 app_tags）
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

OUT_DIR = lib.PROJECT_ROOT / "web" / "server" / "data"


def _article_card(r) -> dict:
    return {
        "uid": r["uid"],
        "title": r["title"] or "（标题待补）",
        "date": r["publish_date"],
        "score": r["value_score"] or 0,
        "type": r["item_type"] or "-",
        "source": SOURCE_NAME.get(r["source"], r["source"]),
        "path": f"/fulltext/{r['content_md_path'].split('fulltext/', 1)[1]}" if r["content_md_path"] else None,
        "url": r["url"],
        "github": json.loads(r["github_urls"] or "[]"),
        "takeaway": r["takeaway"] or "",
        "topics": json.loads(r["topics"] or "[]"),
        "apps": json.loads(r["app_tags"] or "[]"),
        "locked": bool(r["app_lock"]),
    }


SOURCE_NAME = {"aiera": "新智元", "jiqizhixin": "机器之心"}


def run(arts=None) -> dict:
    import yaml
    own = arts is None
    if own:
        conn = lib.init_db()
        arts = conn.execute("SELECT * FROM articles ORDER BY publish_date DESC, id DESC").fetchall()
    else:
        conn = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    classified = [r for r in arts if r["status"] == "classified"]
    # articles.json 收录全部文章（含未分类）：新采集的内容立即可见，type 为 '-'/未分类
    cards = [_article_card(r) for r in arts]

    # ---------- articles.json ----------
    (OUT_DIR / "articles.json").write_text(
        json.dumps(cards, ensure_ascii=False), encoding="utf-8", newline="\n")

    # ---------- topics.json（主题树，按阶段） ----------
    doc = yaml.safe_load((lib.CONFIG_DIR / "tree.yaml").read_text(encoding="utf-8"))
    stage_names = {int(k): v for k, v in (doc.get("stages") or {}).items()}
    tree_list = doc.get("tree", [])
    yaml_order = {n["id"]: i for i, n in enumerate(tree_list)}  # 同阶段内按 tree.yaml 书写顺序
    by_topic = defaultdict(list)
    for r in classified:
        for t in json.loads(r["topics"] or "[]"):
            by_topic[t].append(r)
    nodes = []
    for n in doc.get("tree", []):
        rows = sorted(by_topic.get(n["id"], []),
                      key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True)
        nodes.append({
            "id": n["id"], "name": n["name"], "desc": n.get("desc", ""),
            "stage": int(n.get("stage", 99)), "requires": n.get("requires", []),
            "subtopics": n.get("subtopics", []), "count": len(rows),
            "articles": [_article_card(r) for r in rows[:12]],
        })
    nodes.sort(key=lambda x: (x["stage"], yaml_order.get(x["id"], 999)))
    (OUT_DIR / "topics.json").write_text(
        json.dumps({"stages": stage_names, "nodes": nodes}, ensure_ascii=False), encoding="utf-8", newline="\n")

    # ---------- apptree.json（应用分类） ----------
    adoc = yaml.safe_load((lib.CONFIG_DIR / "app-tree.yaml").read_text(encoding="utf-8"))
    by_app = defaultdict(list)
    for r in classified:
        tags = json.loads(r["app_tags"] or "[]")
        if tags:
            by_app[tags[0]].append(r)  # 首标签 = 加权主分类：聚合面板与看板列一致，一篇只归一列
    apps = []
    for a in adoc.get("apps", []):  # 列顺序 = app-tree.yaml 书写顺序（用户定义的脉络序），不按数量重排
        rows = sorted(by_app.get(a["id"], []),
                      key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True)
        apps.append({
            "id": a["id"], "name": a["name"], "desc": a.get("desc", ""),
            "count": len(rows), "articles": [_article_card(r) for r in rows[:12]],
        })
    (OUT_DIR / "apptree.json").write_text(json.dumps(apps, ensure_ascii=False), encoding="utf-8", newline="\n")

    # ---------- overview.json ----------
    gh_rows = sorted([r for r in classified if r["github_urls"] and r["github_urls"] != "[]"],
                     key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True)
    overview = {
        "generatedAt": lib.now_str(),
        "totals": {
            "articles": len(arts),
            "classified": len(classified),
            "withFulltext": sum(1 for r in arts if r["content_md_path"]),
            "withGithub": len(gh_rows),
            "highScore": sum(1 for r in classified if (r["value_score"] or 0) >= 4),
            "tagCoverage": (
                f"{100 * sum(1 for r in classified if r['app_tags'] and r['app_tags'] != '[]') / len(classified):.1f}%"
                if classified else "-"
            ),
            "bySource": {SOURCE_NAME[s]: sum(1 for r in arts if r["source"] == s) for s in ("jiqizhixin", "aiera")},
        },
        "topGithub": [_article_card(r) for r in gh_rows[:24]],
    }
    (OUT_DIR / "overview.json").write_text(
        json.dumps(overview, ensure_ascii=False), encoding="utf-8", newline="\n")

    result = {"articles": len(cards), "github": len(gh_rows), "out": str(OUT_DIR.relative_to(lib.PROJECT_ROOT))}
    if conn is not None:
        conn.close()
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(), ensure_ascii=False))
