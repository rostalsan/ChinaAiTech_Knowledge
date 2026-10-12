# 分类与价值判定标准（LLM「更新知识库」会话使用）

## 目标
把采集到的文章分成两类去处：**新闻信息**（时效归档）与**有价值的项目/学习信息**（进入知识树和学习计划）。

## 输入
`data/queue/pending.jsonl`，每行一篇待分类文章：

```json
{"uid": "...", "source": "aiera|jiqizhixin", "title": "...", "publish_date": "YYYY-MM-DD",
 "url": "...", "guess": "脚本规则预判", "github": ["https://github.com/owner/repo"],
 "excerpt": "前300字", "text": "正文前2000字纯文本"}
```

## GitHub 硬规则（最高优先级）
代码已对正文做 GitHub 仓库地址硬筛选，结果放在 `github` 字段：
- `github` **非空** → 该文**不可能是普通新闻**：必须在 project / paper / tutorial 中三选一，value_score **至少 3**；
- `project_seed.links` 必须原样收录该 GitHub 地址（便于直接进入复现）；
- 文章主体是发布事件但附开源仓库的，可定 news，但 score 不得低于 3，且 takeaway 必须点出「开源可复现」；
- `github` 为空的 project 判定要格外谨慎：没有仓库就没有直接复现路径，score ≥4 必须给出其他过硬理由。

## 输出
逐行追加写 `data/queue/classified.jsonl`（每行一篇，JSON）：

```json
{"uid": "...", "item_type": "...", "value_score": 3, "takeaway": "...", "topics": ["agent"], "project_seed": null}
```

### item_type（五选一）
| 类型 | 判定 |
|---|---|
| `news` | 新闻快讯：融资、发布事件、人事、活动、榜单、政策。时效价值为主 |
| `paper` | 论文/研究解读：有方法细节、实验或可复现内容 |
| `tutorial` | 教程/实战：手把手、代码走读、how-to、从零搭建 |
| `project` | 项目信息：开源项目/工具/数据集/模型发布，可直接上手 |
| `opinion` | 观点/分析：行业判断、人物观点、深度评论 |

### value_score（对「学习 AI + 做 AI 项目」的价值，1-5）
- **5** 直接可用/必读：可运行代码、完整教程、重要开源/模型发布
- **4** 有实质可借鉴内容：方法细节、架构拆解、一线实践经验
- **3** 值得浏览：有明确信息点但不成体系
- **2** 背景了解：行业动态、普通新闻
- **1** 纯时效/娱乐向

### takeaway
一句话（≤40 字）说清「这篇能让你获得什么」，不写空话。

### topics
1-2 个知识树节点 id（见 `config/tree.yaml`）。现有节点都不合适时用 `"new:建议中文名"` 提议新节点（整理会话收尾时统一裁决是否入树）。

### project_seed（item_type ∈ project/tutorial/paper 且 score≥4 时填写，否则 null）
```json
{"name": "项目/论文/教程名", "links": ["github/paper/官网 URL，来自正文"],
 "what": "做什么、为什么值得", "difficulty": "入门|进阶|高级", "actionable": "建议的动手切入点"}
```
链接必须来自正文 text 中出现的 URL，不得编造。

## 成本控制规则
- 标题/excerpt 已明确是纯新闻（融资/活动/榜单/人物/发布会）→ 直接 `news` + score 1-2，不必细读 text。
- 疑似教程/项目/论文的，必须读 text 再判定。
- 拿不准的往低打分；宁缺毋滥，score≥4 要能说出具体理由。
