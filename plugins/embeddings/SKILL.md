---
name: embeddings
description: 文本向量工具，使用当前 provider 的 embedding 能力为 RAG 生成文本嵌入。
version: "1.0"
category: rag
enabled: true
tags: ["rag", "embedding", "vector"]
---

# 文本嵌入

调用当前 provider 的 `embedding` 能力生成文本向量。需要配置 `embedding_model`。
