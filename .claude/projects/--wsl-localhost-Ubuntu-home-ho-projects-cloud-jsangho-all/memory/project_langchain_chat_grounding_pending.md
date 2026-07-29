---
name: project-langchain-chat-grounding-pending
description: LangChain chatbot (/chat/langchain) gives stale answers on current-events questions (e.g. sports results) — fix deferred by user request 2026-07-28
metadata: 
  node_type: memory
  type: project
  originSessionId: ed9c96cf-9fff-4705-bda5-645c56d2ced0
  modified: 2026-07-28T06:41:45.006Z
---

The LangChain chatbot at `/chat/langchain` (backed by `fastapi/apps/admin/adapter/outbound/repositories/langchain_chat_repository.py`, `ChatGoogleGenerativeAI` model `gemini-3.5-flash`) answers purely from training data — no live grounding — so questions about recent events (sports scores, etc.) can come back outdated or hallucinated.

**Tried and reverted 2026-07-28:** binding Google Search grounding via `.bind_tools([{"google_search": {}}])`. It immediately hit `429 RESOURCE_EXHAUSTED` on the production Gemini API key — this key appears to have zero grounding quota (likely a free-tier project without billing enabled; the key already showed billing-gated messaging elsewhere in `main.py`'s `/chat` endpoint). Plain (non-grounded) generation on the same key works fine. Reverted immediately since it broke the chatbot outright rather than just being occasionally stale.

**Why deferred:** user explicitly said to hold off and revisit later (2026-07-28), not urgent.

**How to apply — options for whoever picks this back up:**
1. Enable billing on the Google AI Studio project backing this `GEMINI_API_KEY`, then re-add the `bind_tools([{"google_search": {}}])` call (see git history around commit `8d8c69b`/`7e385a7` on `ho` for the exact diff that was tried and reverted).
2. Or: for domain-specific questions (destination=`exaone_rag` from [[semantic routing]]), actually route to the existing `soccer` app's real pgvector-backed RAG data instead of bare Gemini — currently `destination`/`entities` from semantic routing are computed but not used to change behavior in `LangchainChatRepository`, so this would be new wiring, not just a config flip.
3. Or leave as-is; the chatbot is explicitly disclaimed ("AI가 생성한 답변이라 부정확할 수 있어요") in the UI already.

Related: this repo's semantic routing itself was reworked the same day to a local embedding classifier (`intfloat/multilingual-e5-small` via `EmbeddingRouterGenerator`, `SEMANTIC_ROUTING_PROVIDER=embedding`) for latency, unrelated to this staleness issue.
