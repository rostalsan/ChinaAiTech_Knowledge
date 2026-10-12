# 「更新知识库」整理会话 SOP

> 用户说「更新知识库」时，LLM 按本 SOP 执行。这是系统里唯一需要 LLM 重度参与的环节。

1. 读 `config/classify.md`（判定标准）和 `config/tree.yaml`（可用节点）。
2. 读 `data/queue/pending.jsonl`（全部积压）。超过 50 篇时分批，每批 ≤50 篇，写完一批再读下一批。
3. 按标准逐篇判定，**追加**写 `data/queue/classified.jsonl`（JSONL）。
4. 运行 `python scripts/ingest_classified.py`（合并主档 + 自动重建 kb/ 的索引、新闻快讯、主题库）。
5. 查看新出现的 `new:*` 主题提议，裁决是否加入 `config/tree.yaml`（加入则同步修改）。
6. 重写 `learning/knowledge-tree.md`：
   - 结构 = tree.yaml 骨架（含 stage 阶段与 requires 前置）+ 实际文章聚集；每个节点写：一句话说明、文章数、3-8 篇代表文章（value_score 高者优先，附本地全文相对链接）、当前缺口（该节点还缺什么系统学习材料）。
   - 顶部写总览（节点数、总文章数、最近更新日期）。
   - `learning/knowledge-tree.html` 由 `build_kb.py` 自动重建（体现从属与先后关系），**不要手改**；树结构变化只改 `config/tree.yaml` 的 stage/requires/subtopics。
7. 重写 `learning/learning-plan.md`：
   - **内容 100% 来自知识库**：只列知识库中筛出的文章（本期新增 + 历史高分），不设「学系统」「动手做」之类外部模板栏目（用户已明确删除，见 2026-10-06 修正）。
   - 结构：必读（价值 5 分）→ 推荐（价值 4 分精选，带 GitHub 仓库的优先）→ 上周完成情况（摘自 progress.md，只引用不改）。
   - 新计划追加在顶部，标日期区间。
8. 重写 `learning/projects.md`：
   - **GitHub 地址必须直接列出**（来自主档 `github_urls` 字段，用户要能从清单一键进入仓库）。
   - 三档分层：一档 = 带 GitHub 且价值 ≥4；二档 = 带 GitHub 价值 3；三档 = 高分无仓库（读原文为主）。
   - 最全清单是自动生成的 `kb/项目库/GitHub速查.md`（build_kb 产出，勿手改）；本文件做精选导读与分层排序。
9. 向用户播报：本次分类 N 篇（类型分布）、知识树变化、本周计划一句话要点。

## 注意
- `learning/progress.md` 由用户手工维护，**只读不写**。
- `kb/` 目录全部由脚本生成，不要手改（下次 build 会覆盖）。
- `classified.jsonl` 里 uid 已存在于主档 status='classified' 的（重复提交），ingest 脚本会自动忽略。
- 会话中途失败：已写入 classified.jsonl 的批次不丢，下次从 pending 里剩余的继续。
- **日常新闻兜底列复核**：`app_tags=["news"]` 是关键词零命中的粗扫兜底，混入误判是常态。整理会话须逐篇复核该列（看标题即可分辨），误判的按主分类改判——写 `data/queue/manual_tags.jsonl`（`{"uid","apps","lock":1}`，先归档旧行）并跑 `python scripts/ingest_manual_tags.py`；确属日常动态的维持不动。关键词法只配做粗筛，精判以 LLM/人工复核为准。
- **人工校准的分类口径**（2026-10-09 依 37 篇锁定样本反推，复核时遵循）：
  - 单标签偏好：主分类一枚即可，非双重明显不叠加二级标签；
  - research=AI4S 真科学与严肃论文；评测跑分、竞赛战报、模型怪癖研究一律维持「日常新闻」，不硬塞科研；
  - Agent 工具/平台/Harness/工程框架 → coding「AI 编程与开发」；Agent 方法论/多智能体规划/模型机理与可解释 → algo「算法优化」；
  - 「日常新闻」的边界（用户校准）：智能汽车等产品发布动态、纯发布/榜单式模型动态、「AI攻克X」式媒体快讯、用量与成本动态 → news；有实际技术细节/开源/效果展示的才进对应实域；超分/残差类具体算法技术 → algo；
  - 机器打标只出主分类单标签；人工页面仍可最多 3 枚（点选顺序即优先级）。
