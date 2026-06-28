# 成员 C · 答辩核心代码说明（审阅版）

---

## 一、与现有 PPT 的对应关系


| PPT 页 | 你讲的内容            | 本文档补充的代码                                |
| ----- | ---------------- | --------------------------------------- |
| 幻灯片 0 | 8000 知识库在架构中的位置  | —（无代码，指架构图即可）                           |
| 幻灯片 1 | 选型 + 630 条 + 三接口 | **§2** 向量库初始化（ChromaDB + BGE-M3）        |
| 幻灯片 2 | 数据飞轮 + 软删除       | **§3** 入库 · **§4** Java 触发 · **§5** 软删除 |
| 幻灯片 3 | 检索原理 + 0.76 效果   | **§6** 相似度检索与 `active` 过滤               |


**可选新增幻灯片 4（附录）标题**：`核心实现 · 数据飞轮代码走读（成员 C）`

---

## 二、向量库初始化 · ChromaDB + BGE-M3

**对应 PPT**：幻灯片 1「技术选型」  
**源文件**：`kb_service/chroma_store.py`（约 99～104 行）

**这段代码在干什么**：服务启动时，在本地 ChromaDB 里 **创建或加载** 名为 `ops_knowledge` 的集合，相当于知识库的「表结构 + 检索规则」。

```
# chroma_store.py · _init_collection()
# 服务启动时执行一次，后面 add / search 都操作这个 collection

def _init_collection(self):
    self.collection = self.client.get_or_create_collection(

        name=COLLECTION_NAME,                    # → "ops_knowledge"

        # 检索算法：用「余弦相似度」比较向量（和 BGE-M3 归一化向量配套）
        metadata={"hnsw:space": "cosine"},

        embedding_function=self.embedding_fn,    # → BGE-M3
    )
    # 结果：self.collection 就是后续操作的「知识库句柄」
```


| 参数                         | 通俗理解                         |
| -------------------------- | ---------------------------- |
| `get_or_create_collection` | 有库就加载，没有就新建（重启服务知识不丢）        |
| `cosine`                   | 两个向量「方向越接近」越相似，适合语义检索        |
| `embedding_function`       | 不用手写向量，Chroma 调用 BGE-M3 自动编码 |


> **答辩一句**：向量库落在本地 `chroma_kb_store/`，用 BGE-M3 编码、余弦相似度检索，满足私有化部署。

---

## 三、数据飞轮入库 · 工单 ID + 语义去重

**对应 PPT**：幻灯片 2 第二步「resolve → add → kb_ticket_{id}」  
**源文件**：`kb_service/chroma_store.py` · `add()`（约 114～146 行）

**这段代码在干什么**：运维处理完工单后，把「用户问题 + 标准答案」写入向量库；**先查重、再入库、再绑工单号**。

```python
# chroma_store.py · add(question, answer, metadata, dedup=True)

# 语义去重（
if dedup and self.count() > 0:
  existing_results = self.search(question, top_k=3)  
  for r in existing_results:
    if r["score"] >= dedup_threshold:                 # 默认阈值 0.90
      # 已有高度相似条目 → 跳过写入，返回已有 ID
      return {"id": dup_id, "duplicate": True, ...}

# 准备元数据
meta = dict(metadata or {})
meta.setdefault("active", True)           # 默认「有效」

ticket_id = meta.get("ticket_id")        
if ticket_id:
  doc_id = f"kb_ticket_{ticket_id}"     # 工单知识用稳定 ID：kb_ticket_42
else:
  doc_id = f"kb_{self.count() + 1}"     # 种子 FAQ / 文档块用 kb_1, kb_2...

text = f"问题：{question}\n答案：{answer}"   
meta.update({"id": doc_id, "question": question, "answer": answer})

# 写入 ChromaDB（BGE-M3 自动把 text 转成向量）
self.collection.add(
  ids=[doc_id],          
  documents=[text],      
  metadatas=[meta],      
)
return {"id": doc_id, "duplicate": False, ...}
```

**对外 HTTP 入口**（成员 B 的 Java 调这个，不用直接调 `add()`）  
**源文件**：`kb_service/main.py`（约 125～141 行）

```python
# main.py · 工单处理完成后，Java POST 到这里

@app.post("/api/kb/add")
async def add_knowledge(req: AddKnowledgeRequest):
    result = store.add(
        question=req.question,              # 用户原始问题（来自工单）
        answer=req.answer,                  # 运维填写的标准答案
        metadata=req.metadata,              # 含 ticket_id、source="ticket"
        dedup=req.skip_if_duplicate,        # 默认 True，开启语义去重
        dedup_threshold=req.dedup_threshold # 默认 0.90
    )
    return AddKnowledgeResponse(id=result["id"], ...)  # 返回 kb_ticket_xx 给 Java
```

> **答辩一句**：不是简单追加，而是先去重，再用工单号生成稳定 ID，删工单时能精确定位。

---

## 四、Java 侧触发飞轮 · resolve 调 8000

**对应 PPT**：幻灯片 2「Java resolve → POST /api/kb/add」  
**源文件**：`TicketController.java`（成员 B 维护，C 提供 8000 接口）

**这段代码在干什么**：运维在后台点「处理完成」→ Java 更新工单状态 → **HTTP 调知识库 add** → 把返回的 ID 存进工单。

```java
// TicketController.java · resolveTicket — 处理工单的入口

@PostMapping("/{id}/resolve")
public ResponseEntity<?> resolveTicket(@PathVariable Long id, ...) {
    ticket.setResolution(request.getResolution());   // 保存运维写的解决方案
    ticket.setOperatorId(request.getOperatorId());
    ticket.setStatus("resolved");                    // 标记为已处理

    // 调 Python 知识库，把问答写入 8000
    String kbEntryId = syncToKnowledgeBase(
        id,                          // 工单号 → 生成 kb_ticket_{id}
        ticket.getUserQuestion(),    // 用户当时问的问题
        request.getResolution()     // 运维标准答案
    );

    if (kbEntryId != null) {
        ticket.setKbEntryId(kbEntryId);  // 回写 ID，删工单时可再定位
    }
    ticketRepository.save(ticket);
    return ResponseEntity.ok("工单处理完成，并已同步更新至本地知识库。");
}
```

```java
// syncToKnowledgeBase — 实际发 HTTP 请求给 kb_service

Map<String, Object> metadata = new HashMap<>();
metadata.put("ticket_id", String.valueOf(ticketId));  // 传给 Python 生成 kb_ticket_
metadata.put("source", "ticket");                       // 标记来源是工单飞轮

Map<String, Object> body = new HashMap<>();
body.put("question", question);
body.put("answer", answer);
body.put("metadata", metadata);

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://127.0.0.1:8000/api/kb/add"))  
    .header("Content-Type", "application/json; charset=UTF-8")
    .POST(HttpRequest.BodyPublishers.ofString(requestBody, UTF_8))
    .build();
// 解析响应 JSON 里的 "id" 字段返回
```

> **答辩一句**：业务在 Java、向量在 Python，通过 REST 解耦；B 在 resolve 里调一次 add 就完成飞轮入库。

---

## 五、软删除 · 删工单同步停用知识

**对应 PPT**：幻灯片 2 第四步「soft-delete → active=false」

### Python 侧：标记无效，不删向量

**源文件**：`kb_service/chroma_store.py` · `soft_delete()`（约 215～245 行）

```python
# chroma_store.py · soft_delete — 只改是否有效标记

def soft_delete(doc_id=None, ticket_id=None):
    # 优先用 ticket_id 定位
    target_id = f"kb_ticket_{ticket_id}" if ticket_id else doc_id

    existing = self.collection.get(ids=[target_id], include=["metadatas"])
    if not existing.get("ids"):
        return {"success": False, "message": "条目不存在"}

    meta = dict(existing["metadatas"][0])
    if not _is_active(meta):
        return {"success": True, "already_inactive": True}  # 幂等：已删过不报错

    # 只改元数据，向量还在磁盘上（可审计）
    meta["active"] = False
    self.collection.update(ids=[target_id], metadatas=[meta])
    return {"success": True, "id": target_id}
```

### Java 侧：删工单前调 soft-delete

**源文件**：`TicketController.java` · `deleteTicket()`（约 53～62 行）

```java
@DeleteMapping("/{id}")
public ResponseEntity<?> deleteTicket(@PathVariable Long id) {
    if ("resolved".equals(ticket.getStatus())) {
        // 只有已处理的工单才有关联知识，需要同步停用
        softDeleteFromKnowledgeBase(ticket);  // POST → /api/kb/soft-delete
    }
    ticketRepository.delete(ticket);        // 再删 MySQL 里的工单记录
    return ResponseEntity.ok("工单已成功删除，关联知识库条目已同步停用。");
}
```


| 对比   | 物理删除  | 软删除（本项目）                   |
| ---- | ----- | -------------------------- |
| 向量数据 | 从库中移除 | 保留在 `chroma_kb_store/`     |
| 检索   | 自然找不到 | `search` 过滤 `active=false` |
| 优点   | 彻底干净  | 可审计、可恢复、实现简单               |


> **答辩一句**：软删除后检索自动忽略，用户侧效果和真删一样，但数据仍可追溯。

---

## 六、检索实现 · 相似度换算 + 有效知识过滤

**对应 PPT**：幻灯片 3「BGE-M3 向量化 → 余弦相似度 → score≥0.60」  
**源文件**：`kb_service/chroma_store.py` · `search()`（约 178～212 行）

**这段代码在干什么**：用户/RAG 提问 → BGE-M3 转向量 → 在库里找最相似的 Q&A → **过滤已软删除的** → 返回 Top-K + 分数。

```python
# 工具函数：Chroma 返回的是距离，相似度要换算
def _distance_to_score(distance):
    # distance 越小越相似 → 转成 0~1，越大越相似
    return max(0.0, min(1.0, 1.0 - float(distance)))
    # 例：distance=0.24 → score=0.76（账号冻结实测约这个水平）
```

```python
# chroma_store.py · search(query, top_k=5)

def search(self, query, top_k=5, active_only=True):
    # 多取一些候选（top_k 的 5 倍），因为后面要过滤掉 inactive 的
    fetch_k = min(max(top_k * 5, top_k), total)

    results = self.collection.query(
        query_texts=[query],              # 用户问句 → BGE-M3 自动编码
        n_results=fetch_k,
        include=["metadatas", "documents", "distances"],
    )

    output = []
    for i, doc_id in enumerate(ids):
        meta = metadatas[i]

        # 软删除过滤：active=false 的条目直接跳过
        if active_only and not _is_active(meta):
            continue

        score = _distance_to_score(distances[i])   # 转成 0~1 相似度
        output.append({
            "id": meta.get("id", doc_id),
            "question": meta.get("question"),
            "answer": meta.get("answer"),
            "score": score,                         # RAG 用 ≥0.60 作可靠上下文
        })
        if len(output) >= top_k:
            break
    return output
```

**检索流程简图**：

```
用户问句 "账号冻结怎么处理"
    ↓ BGE-M3 编码
向量 query_vec
    ↓ Chroma 余弦检索
候选 N 条（含 distance）
    ↓ 过滤 active=false
有效候选
    ↓ distance → score
Top-K 结果（score 最高优先）
```

**实测效果**：

- 问句：`账号冻结怎么处理`
- Top1 `score ≈ 0.76`，答案含课题示例网址与热线

> **答辩一句**：不是关键词匹配，是向量语义相似度；软删除的知识不会进入结果集。

---

## 七、（可选）文档切片 

**对应 PPT**：幻灯片 3「文档按标题切片」— 老师问「630 条怎么来的」  
**源文件**：`kb_service/ingest.py` · `make_question()`（约 48～51 行）

**这段代码在干什么**：Markdown 每个 `###` 标题是一块知识；把标题改写成 **自然语言问句**，再和正文组成 Q&A 入库。

```python
# ingest.py · 把三级标题转成可检索的问句

def make_question(doc_name, h2_title, h3_title):
    # 去掉标题前的编号，如 "3.1.2 账号冻结" → "账号冻结"
    clean = re.sub(r"^\d+(\.\d+)*\s*", "", h3_title).strip()

    # 标题里已有“怎么/如何”→ 直接当问句
    if re.search(r"(怎么|如何|为什么|...)", clean):
        return f"{doc_name}：{clean}"         

    # 标题是「排查步骤」类 → 改写成「怎么排查xxx？」
    # 标题是「解决方法」类 → 改写成「xxx怎么解决？」
    # 其他规则见 ingest.py 完整函数
```

> **答辩一句（15 秒）**：11 份文档按 `###` 切片 + 500 条种子 FAQ，`rebuild_kb.py` 一次性写入 ChromaDB，共约 630 条。

---

## 八、可选放入 PPT 的伪代码

### 左栏：飞轮入库

```
# 工单 resolve 之后 · chroma_store.add

① 语义去重
   if 库里已有相似问题 and 相似度 >= 0.90:
       return  # 不重复写

② 生成稳定 ID
   doc_id = "kb_ticket_" + 工单号    

③ 写入向量库
   collection.add(
       id = doc_id,
       text = "问题：... 答案：...",
       metadata = { active: True, ticket_id: 42 }
   )
   # BGE-M3 自动把 text 转成向量存入 chroma_kb_store/
```

### 右栏：检索过滤

```
# 用户提问时 · chroma_store.search

① 问句 → BGE-M3 → 向量 query_vec

② 在 Chroma 里找最相似的 N 条
   results = collection.query(query_vec, n=top_k×5)

③ 过滤 + 打分
   for each result:
       if metadata.active == False: skip    # 软删除的不要
       score = 1 - cosine_distance          # 转成 0~1 相似度

④ 返回 score 最高的 top_k 条
   # 成员 A 的 RAG 只用 score >= 0.60 的作上下文
```

`Java resolve → POST /api/kb/add` · `Java delete → POST /api/kb/soft-delete`

---

## 九、附录页口播

> 入库在 `add`：先语义去重，再用 `kb_ticket_{工单号}` 作稳定 ID，默认 `active` 为真。
>
> 检索在 `search`：距离转成 0～1 的相似度，并过滤 `active` 为 false 的条目。
>
> Java 不直接碰向量库，只在 resolve 和 delete 时 HTTP 调我的 add 和 soft-delete。这就是飞轮在代码里的闭环。

---

*审阅版 v2 · 代码块已补充中文注释与流程说明。对齐 `成员C-答辩PPT与逐字稿.md` 四页结构。*