# -*- coding: utf-8 -*-
"""构建人读知识库层（kb/）与待分类队列。整体可重复重建（幂等）。

  kb/INDEX.md                全库索引与统计
  kb/新闻快讯/YYYY-MM.md     按月-日-事件分组的快讯流（全部文章）
  kb/主题库/<节点>.md        已分类文章按知识树节点归档
  data/queue/pending.jsonl   待 LLM 分类的积压队列（每次重建，含规则预判 guess）
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

SOURCE_NAME = {"aiera": "新智元", "jiqizhixin": "机器之心"}

VALUE_KW = ["开源", "github", "教程", "实战", "手把手", "论文", "复现", "工具", "框架", "实现",
            "代码", "从零", "入门", "指南", "调优", "实践", "拆解", "源码", "部署", "微调",
            "训练", "prompt", "Prompt", "MCP", "RAG", "Agent", "智能体", "工作流", "权重", "数据集"]
NEWS_KW = ["融资", "估值", "收购", "IPO", "上市", "发布会", "大会", "峰会", "论坛", "获奖",
           "任命", "离职", "榜单", "排行榜", "纳斯达克", "监管", "起诉", "裁员", "首款", "发布"]


def load_tree() -> list:
    import yaml
    tree = yaml.safe_load((lib.CONFIG_DIR / "tree.yaml").read_text(encoding="utf-8"))
    return tree.get("tree", [])


_TREE_HTML_TEMPLATE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>AI 知识树 · 从属与学习先后关系</title>
<style>
 body{font-family:"Microsoft YaHei",system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1f2430}
 header{padding:20px 28px;background:#101425;color:#fff}
 header h1{margin:0 0 6px;font-size:22px} header p{margin:0;opacity:.75;font-size:13px}
 .lane{position:relative;padding:16px 28px 16px 6px}
 .lane h2{font-size:16px;margin:0 0 10px}
 .lane-dot{position:absolute;left:-22px;top:20px;width:12px;height:12px;border-radius:50%;background:#3b6ef5;box-shadow:0 0 0 3px rgba(59,110,245,.15)}
 #lanes{position:relative;padding-left:22px}
 #lanes::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;background:#e3e6ee}
 .nodes{display:flex;flex-wrap:wrap;gap:12px}
 .card{background:#fff;border:1px solid #e3e6ee;border-radius:10px;padding:12px 14px;width:260px;cursor:pointer;box-shadow:0 1px 3px rgba(16,20,37,.06)}
 .card:hover{border-color:#5b7cfa}
 .card b{font-size:15px} .card .d{font-size:12px;color:#7a8194;margin-top:4px;line-height:1.5}
 .card .c{margin-top:8px;font-size:12px;color:#3b6ef5}
 .card .req{font-size:11px;color:#a0a6b5;margin-top:6px}
 #panel{position:fixed;top:0;right:-470px;width:450px;height:100%;background:#fff;box-shadow:-4px 0 16px rgba(0,0,0,.12);transition:right .2s;overflow-y:auto;padding:20px 22px;box-sizing:border-box}
 #panel.open{right:0}
 #panel h3{margin-top:0}
 .art{margin:10px 0;padding:10px 12px;background:#f6f7f9;border-radius:8px;font-size:13px}
 .art a{color:#1f2430;text-decoration:none;font-weight:600}
 .art a:hover{color:#3b6ef5}
 .art .meta{color:#7a8194;font-size:12px;margin-top:3px}
 .tag{display:inline-block;background:#e8eeff;color:#2f5fe0;border-radius:4px;padding:0 6px;font-size:11px;margin-right:6px}
 .gh{color:#0b7a3b;font-size:12px;word-break:break-all;margin-top:3px}
 .close{float:right;cursor:pointer;color:#888;font-size:18px}
 ul.sub-list{margin:6px 0 0;padding-left:18px;font-size:12px;color:#5a6172}
</style></head>
<body>
<header><h1>AI 知识树 · 从属与学习先后关系</h1>
<p>自上而下为建议学习顺序（先后关系）；点开节点查看其子主题与代表文章（从属关系）。生成于 __GENERATED__。</p></header>
<div id="lanes"></div>
<div id="panel"><span class="close" onclick="document.getElementById('panel').classList.remove('open')">✕</span><div id="panel-body"></div></div>
<script>
const DATA = __DATA__;
const STAGE_NAMES = __STAGES__;
const lanes = document.getElementById('lanes');
const stages = [...new Set(DATA.map(n=>n.stage))].sort((a,b)=>a-b);
stages.forEach((s)=>{
  const lane=document.createElement('div');lane.className='lane';
  lane.innerHTML='<div class="lane-dot"></div><h2>第 '+s+' 阶段 · '+(STAGE_NAMES[s]||'')+'</h2><div class="nodes"></div>';
  const wrap=lane.querySelector('.nodes');
  DATA.filter(n=>n.stage===s).forEach(n=>{
    const c=document.createElement('div');c.className='card';
    c.innerHTML='<b>'+n.name+'</b><div class="d">'+n.desc+'</div><div class="c">'+n.count+' 篇文章 · 点开 →</div>'+
      (n.requires.length?'<div class="req">前置：'+n.requires.join('、')+'</div>':'');
    c.onclick=()=>openNode(n);
    wrap.appendChild(c);
  });
  lanes.appendChild(lane);
});
function openNode(n){
  const p=document.getElementById('panel-body');
  let h='<h3>'+n.name+'</h3><p style="font-size:12px;color:#7a8194">'+n.desc+'</p>';
  if(n.subtopics&&n.subtopics.length){h+='<b style="font-size:13px">子主题（从属）</b><ul class="sub-list">'+
    n.subtopics.map(s=>'<li>'+s+'</li>').join('')+'</ul>';}
  h+='<b style="font-size:13px">代表文章（按价值分）</b>';
  h+=n.articles.map(a=>'<div class="art"><a href="'+a.p+'" target="_blank">'+a.t+'</a>'+
    '<div class="meta"><span class="tag">'+a.s+'分</span><span class="tag">'+a.ty+'</span>'+a.d+' · '+a.src+'</div>'+
    (a.gh?'<div class="gh">GitHub: <a href="'+a.gh[0]+'" target="_blank">'+a.gh[0]+'</a></div>':'')+'</div>').join('');
  p.innerHTML=h;
  document.getElementById('panel').classList.add('open');
}
</script></body></html>
"""


def write_tree_html(arts) -> None:
    """生成 learning/knowledge-tree.html：阶段=先后关系，节点内子主题/文章=从属关系。"""
    import yaml
    doc = yaml.safe_load((lib.CONFIG_DIR / "tree.yaml").read_text(encoding="utf-8"))
    tree = doc.get("tree", [])
    stage_names = {int(k): v for k, v in (doc.get("stages") or {}).items()}
    name_by_id = {n["id"]: n["name"] for n in tree}

    by_topic: dict[str, list] = {}
    for r in arts:
        if r["status"] != "classified":
            continue
        try:
            topics = json.loads(r["topics"] or "[]")
        except json.JSONDecodeError:
            continue
        for t in topics:
            by_topic.setdefault(t, []).append(r)

    data = []
    for n in tree:
        rows = by_topic.get(n["id"], [])
        rows = sorted(rows, key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True)
        articles = []
        for r in rows[:10]:
            if r["content_md_path"]:
                link = "../" + r["content_md_path"]
            else:
                link = r["url"]
            articles.append({
                "t": r["title"] or "（标题待补）", "p": link,
                "s": r["value_score"] or 0, "ty": r["item_type"] or "-",
                "d": r["publish_date"], "src": SOURCE_NAME.get(r["source"], r["source"]),
                "gh": json.loads(r["github_urls"] or "[]"),
            })
        data.append({
            "id": n["id"], "name": n["name"], "desc": n.get("desc", ""),
            "stage": int(n.get("stage", 99)),
            "requires": [name_by_id.get(x, x) for x in n.get("requires", [])],
            "subtopics": n.get("subtopics", []), "count": len(rows), "articles": articles,
        })
    yaml_order = {n["id"]: i for i, n in enumerate(tree)}  # 同阶段内按 tree.yaml 书写顺序
    data.sort(key=lambda x: (x["stage"], yaml_order.get(x["id"], 999)))
    html = (_TREE_HTML_TEMPLATE
            .replace("__GENERATED__", lib.now_str())
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__STAGES__", json.dumps({str(k): v for k, v in stage_names.items()}, ensure_ascii=False)))
    out = lib.LEARNING_DIR / "knowledge-tree.html"
    out.write_text(html, encoding="utf-8", newline="\n")


def read_fulltext_body(rel_path: str) -> str:
    p = lib.PROJECT_ROOT / rel_path
    if not p.exists():
        return ""
    t = p.read_text(encoding="utf-8")
    if t.startswith("---"):
        end = t.find("\n---", 3)
        if end >= 0:
            return t[end + 4:].strip()
    return t


def presort(title: str, body: str) -> str:
    s = (title or "") + " " + (body or "")[:400]
    v = sum(1 for k in VALUE_KW if k in s)
    n = sum(1 for k in NEWS_KW if k in s)
    if v >= 2 and v > n:
        return "value"
    if n >= 1 and n > v:
        return "news"
    return "unsure"


def _fulltext_link(rel_path: str, from_depth: int) -> str:
    """生成从 kb/<from_depth> 层指向全文的相对链接。depth: INDEX=1, 子目录=2"""
    prefix = "../" * from_depth
    return f"{prefix}{rel_path}"


def _badge(r) -> str:
    parts = [SOURCE_NAME.get(r["source"], r["source"])]
    if r["item_type"]:
        parts.append(r["item_type"])
    if r["value_score"]:
        parts.append(f"{r['value_score']}分")
    return " · ".join(parts)


def rebuild(conn=None) -> dict:
    own = conn is None
    conn = conn or lib.init_db()
    tree = load_tree()
    tree_name = {n["id"]: n["name"] for n in tree}
    stats = {"pending_count": 0, "months": 0, "topic_files": 0}

    arts = conn.execute("SELECT * FROM articles ORDER BY publish_date DESC, id DESC").fetchall()

    # ---------- GitHub 硬筛选：为未扫描过的文章提取正文中的仓库地址 ----------
    gh_scanned = 0
    for r in arts:
        if r["github_urls"] is not None or not r["content_md_path"]:
            continue
        urls = lib.extract_github_urls(read_fulltext_body(r["content_md_path"]))
        conn.execute("UPDATE articles SET github_urls=? WHERE id=?",
                     (json.dumps(urls, ensure_ascii=False), r["id"]))
        gh_scanned += 1
    if gh_scanned:
        conn.commit()
        arts = conn.execute("SELECT * FROM articles ORDER BY publish_date DESC, id DESC").fetchall()
    stats["github_scanned"] = gh_scanned
    stats["github_articles"] = sum(1 for r in arts if r["github_urls"] and r["github_urls"] != "[]")

    # ---------- 应用分类标签（第二套知识脉络：时间线×应用） ----------
    try:
        import yaml
        doc = yaml.safe_load((lib.CONFIG_DIR / "app-tree.yaml").read_text(encoding="utf-8"))
        app_rules = [(a["id"], a.get("keywords", [])) for a in doc.get("apps", [])]
        app_ids = {a["id"] for a in doc.get("apps", [])}
        # 兜底域（日常新闻）：仅当所有实域零命中时打入，不参与关键词竞争——权重默认最低
        fallback_id = doc.get("fallback", "") if doc.get("fallback", "") in app_ids else ""
    except Exception:
        app_rules = []
        fallback_id = ""
    tagged = 0
    for r in arts:
        # 人工锁定（审阅页手工打标）的文章永不参与机器打标；运维纪律：全量重算清空
        # app_tags 时必须带 WHERE app_lock=0，否则会抹掉人工锁定标签。
        if r["app_lock"]:
            continue
        # 空数组也重算：历史空标签多因旧 takeaway（≈标题）匹配不上；复核改判后 takeaway
        # 变丰富、且匹配文本加入全文前 2000 字，覆盖率大幅提升。已打标的 820 篇不重算。
        if r["app_tags"] is not None and r["app_tags"] != "[]":
            continue
        if not app_rules:
            break
        # 位置加权打分：标题 4 > 摘要 2 > 全文前 2000 字 1。得分降序 = 主分类优先，
        # 首标签为主分类（看板按它归列，不跨列重复），同分按 yaml 书写序。
        title, takeaway = r["title"] or "", r["takeaway"] or ""
        ft = read_fulltext_body(r["content_md_path"])[:2000] if r["content_md_path"] else ""
        scored = []
        for order, (aid, kws) in enumerate(app_rules):
            s = 0
            for k in kws:
                if k in title:
                    s += 4
                elif k in takeaway:
                    s += 2
                elif k in ft:
                    s += 1
            if s > 0:
                scored.append((s, -order, aid))
        scored.sort(reverse=True)
        # 单标签主分类 + 置信门槛（依人工校准 2026-10-09）：最高分 <2 即仅全文噪声命中、
        # 标题摘要毫无迹象，视为零命中走「日常新闻」兜底，交 LLM/人工复核。
        if scored and scored[0][0] >= 2:
            tags = [scored[0][2]]
        elif fallback_id:
            tags = [fallback_id]
        else:
            tags = []
        conn.execute("UPDATE articles SET app_tags=? WHERE id=?",
                     (json.dumps(tags, ensure_ascii=False), r["id"]))
        tagged += 1
    if tagged:
        conn.commit()
        arts = conn.execute("SELECT * FROM articles ORDER BY publish_date DESC, id DESC").fetchall()
    stats["app_tagged"] = tagged

    # ---------- 待分类队列 ----------
    lib.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    qpath = lib.QUEUE_DIR / "pending.jsonl"
    with qpath.open("w", encoding="utf-8", newline="\n") as f:
        for r in arts:
            if r["status"] != "pending" or not r["content_md_path"]:
                continue
            body = read_fulltext_body(r["content_md_path"])
            text = lib.md_to_plaintext(body, 2000)
            extra = json.loads(r["extra"] or "{}")
            rec = {
                "uid": r["uid"], "source": r["source"],
                "title": r["title"], "publish_date": r["publish_date"], "url": r["url"],
                "guess": presort(r["title"] or "", body),
                "github": json.loads(r["github_urls"] or "[]"),  # 硬筛选：非空则优先按项目/论文处理
                "excerpt": (extra.get("excerpt") or text[:300] or ""),
                "text": text,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["pending_count"] += 1

    # ---------- INDEX.md ----------
    by_source = defaultdict(lambda: {"n": 0, "full": 0, "pending": 0, "classified": 0})
    type_dist = defaultdict(int)
    score_dist = defaultdict(int)
    topic_count = defaultdict(int)
    for r in arts:
        s = by_source[r["source"]]
        s["n"] += 1
        if r["content_md_path"]:
            s["full"] += 1
        if r["status"] == "pending":
            s["pending"] += 1
        if r["status"] == "classified":
            s["classified"] += 1
        if r["item_type"]:
            type_dist[r["item_type"]] += 1
        if r["value_score"]:
            score_dist[r["value_score"]] += 1
        try:
            for t in json.loads(r["topics"] or "[]"):
                topic_count[t] += 1
        except json.JSONDecodeError:
            pass
    cross_groups = conn.execute(
        "SELECT COUNT(*) FROM events WHERE sources LIKE '%,%'").fetchone()[0]
    total_groups = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    L = [f"# AI 知识库索引", "",
         f"> 自动生成于 {lib.now_str()}。kb/ 全部由脚本重建，勿手改；个人批注写 learning/。", "",
         "## 总览", "",
         "| 源 | 文章 | 有全文 | 待分类 | 已分类 |", "|---|---:|---:|---:|---:|"]
    for src in ("jiqizhixin", "aiera"):
        s = by_source.get(src, {"n": 0, "full": 0, "pending": 0, "classified": 0})
        L.append(f"| {SOURCE_NAME[src]} | {s['n']} | {s['full']} | {s['pending']} | {s['classified']} |")
    tot = [sum(s[k] for s in by_source.values()) for k in ("n", "full", "pending", "classified")]
    L.append(f"| 合计 | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} |")
    L += ["", f"- 同事件组：{total_groups} 组（跨源 {cross_groups} 组）",
          f"- 带 GitHub 仓库的文章：{stats['github_articles']} 篇 → 速查表 [项目库-GitHub速查.md](项目库-GitHub速查.md)",
          f"- 知识树 HTML 视图：[learning/knowledge-tree.html](../learning/knowledge-tree.html)"]
    if type_dist:
        L.append("- 类型分布：" + " · ".join(f"{k} {v}" for k, v in sorted(type_dist.items())))
    if score_dist:
        L.append("- 价值分布：" + " · ".join(f"{k}分 {v}" for k, v in sorted(score_dist.items(), reverse=True)))
    L += ["", "## 知识树分布", "", "| 节点 | 名称 | 已挂载 |", "|---|---|---:|"]
    for n in tree:
        L.append(f"| {n['id']} | {n['name']} | {topic_count.get(n['id'], 0)} |")
    extra_topics = {k: v for k, v in topic_count.items() if k not in tree_name}
    if extra_topics:
        L.append("")
        L.append("未入树节点：" + " · ".join(f"{k}({v})" for k, v in extra_topics.items()))
    L += ["", "## 最近入库", ""]
    for r in arts[:20]:
        full = f"[全文]({_fulltext_link(r['content_md_path'], 1)})" if r["content_md_path"] else "（待补）"
        L.append(f"- {r['publish_date']} 【{SOURCE_NAME.get(r['source'], r['source'])}】"
                 f"{r['title'] or '（标题待补）'} · {full} · [原文]({r['url']})")
    L += ["", "## 使用", "",
         "- 日常采集：`python scripts/run_all.py`（每日自动化已配置）",
         "- 整理知识库：对我说「更新知识库」（LLM 按 config/curate-sop.md 执行）",
         "- 知识树与学习计划在 `learning/`，由 LLM 整理会话维护", ""]
    (lib.KB_DIR / "INDEX.md").write_text("\n".join(L), encoding="utf-8", newline="\n")

    # ---------- 新闻快讯（按月） ----------
    by_month = defaultdict(list)
    for r in arts:
        if r["publish_date"]:
            by_month[r["publish_date"][:7]].append(r)
    news_dir = lib.KB_DIR / "新闻快讯"
    news_dir.mkdir(parents=True, exist_ok=True)
    for old in news_dir.glob("*.md"):
        old.unlink()
    for month in sorted(by_month, reverse=True):
        rows = by_month[month]
        groups_in_month = {r["dedup_group"] for r in rows if r["dedup_group"]}
        L = [f"# 新闻快讯 · {month}", "",
             f"> 共 {len(rows)} 篇 / {len(groups_in_month)} 组。自动生成。", ""]
        by_day = defaultdict(list)
        for r in rows:
            by_day[r["publish_date"]].append(r)
        for day in sorted(by_day, reverse=True):
            L.append(f"## {day[5:]}")
            L.append("")
            seen_groups = set()
            for r in by_day[day]:
                g = r["dedup_group"]
                if g and g in seen_groups:
                    continue
                title = r["title"] or "（标题待补）"
                full = f"[全文]({_fulltext_link(r['content_md_path'], 2)})" if r["content_md_path"] else "（待补正文）"
                L.append(f"- **{title}**（{_badge(r)}）{r['takeaway'] or ''}")
                L.append(f"  {full} ｜ [原文]({r['url']})")
                if g:
                    seen_groups.add(g)
                    members = [x for x in by_day[day] if x["dedup_group"] == g and x["id"] != r["id"]]
                    for m in members:
                        mfull = f"[全文]({_fulltext_link(m['content_md_path'], 2)})" if m["content_md_path"] else ""
                        L.append(f"  - 同事件：{m['title'] or '（标题待补）'}（{SOURCE_NAME.get(m['source'], m['source'])}）{mfull}")
            L.append("")
        (news_dir / f"{month}.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
        stats["months"] += 1

    # ---------- 主题库（按知识树节点） ----------
    topic_dir = lib.KB_DIR / "主题库"
    topic_dir.mkdir(parents=True, exist_ok=True)
    for old in topic_dir.glob("*.md"):
        old.unlink()
    node_articles = defaultdict(list)
    for r in arts:
        if r["status"] != "classified" or not r["content_md_path"]:
            continue
        try:
            topics = json.loads(r["topics"] or "[]")
        except json.JSONDecodeError:
            continue
        for t in topics:
            if t in tree_name:
                node_articles[t].append(r)
    for node in tree:
        rows = node_articles.get(node["id"], [])
        if not rows:
            continue
        L = [f"# {node['name']}", "",
             f"> {node['desc']} ｜ 共 {len(rows)} 篇 ｜ 自动生成", ""]
        for r in sorted(rows, key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True):
            seed_info = ""
            if r["project_seed"]:
                try:
                    seed = json.loads(r["project_seed"])
                    if isinstance(seed, dict) and seed.get("name"):
                        seed_info = f" ｜ 项目：{seed.get('name')}（{seed.get('difficulty', '')}）"
                except json.JSONDecodeError:
                    pass
            gh = json.loads(r["github_urls"] or "[]")
            gh_info = f" ｜ GitHub: {gh[0]}" if gh else ""
            L.append(f"- **[{r['title']}]({_fulltext_link(r['content_md_path'], 2)})**"
                     f"（{r['value_score']}分 · {r['item_type']} · {r['publish_date']} · {SOURCE_NAME.get(r['source'], r['source'])}）")
            if r["takeaway"]:
                L.append(f"  {r['takeaway']}")
            L.append(f"  [原文]({r['url']}){gh_info}{seed_info}")
        L.append("")
        safe_name = f"{node['id']}-{node['name']}.md".replace("/", "-")
        (topic_dir / safe_name).write_text("\n".join(L), encoding="utf-8", newline="\n")
        stats["topic_files"] += 1

    # ---------- 项目库-GitHub速查（代码硬筛选，自动生成） ----------
    gh_dir = lib.KB_DIR / "项目库"
    gh_dir.mkdir(parents=True, exist_ok=True)
    gh_rows = [r for r in arts if r["github_urls"] and r["github_urls"] != "[]"]
    gh_rows.sort(key=lambda x: (x["value_score"] or 0, x["publish_date"] or ""), reverse=True)
    G = ["# 项目库 · GitHub 速查", "",
         f"> 代码硬筛选自动生成于 {lib.now_str()}：正文中出现 GitHub 仓库地址的全部文章，"
         "可参考复现，优先级高于无仓库项目。勿手改。", ""]
    for r in gh_rows:
        gh = json.loads(r["github_urls"])
        badge = _badge(r) if r["item_type"] else "未分类"
        full = f"[全文]({_fulltext_link(r['content_md_path'], 1)})" if r["content_md_path"] else "（待补正文）"
        G.append(f"### [{r['title'] or '（标题待补）'}]({_fulltext_link(r['content_md_path'], 1) if r['content_md_path'] else r['url']})")
        G.append(f"- 仓库：**{' ｜ '.join(gh)}**")
        G.append(f"- {badge} · {r['publish_date']} · {full} ｜ [原文]({r['url']})")
        if r["takeaway"]:
            G.append(f"- {r['takeaway']}")
        G.append("")
    (gh_dir / "GitHub速查.md").write_text("\n".join(G), encoding="utf-8", newline="\n")
    stats["github_listed"] = len(gh_rows)

    # ---------- 知识树 HTML（从属 + 先后关系，自动生成） ----------
    write_tree_html(arts)
    stats["tree_html"] = True

    # ---------- Web 数据导出（供 npm 前后端使用；失败不影响主流程） ----------
    try:
        import export_web
        export_web.run(arts)
        stats["web_export"] = True
    except Exception as e:  # noqa: BLE001
        stats["web_export"] = f"skipped({str(e)[:120]})"

    if own:
        conn.close()
    return stats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(rebuild(), ensure_ascii=False))
