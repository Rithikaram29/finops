"""
policy_rag.py
-------------
RAG over the policy corpus for the FinOps Agent.

    chunk  ->  BM25 index + dense embeddings  ->  hybrid search (RRF)  ->  citations

search_policy(query, k) is the TOOL the agent calls. Like matching.py it ONLY
retrieves -- it never calls the LLM. The agent passes the returned chunks (with
their `doc` citation) plus the discrepancy evidence to the LLM, which writes the
grounded, cited answer.

Embeddings are pluggable:
    StubEmbedder   - deterministic, offline, NOT semantic. Wiring/tests only.
    LocalEmbedder  - sentence-transformers, runs on your machine, no API key.
    ApiEmbedder    - OpenAI embeddings, needs OPENAI_API_KEY.
Swap one line in build_index(...) to go live. See __main__.
"""

import re
import math
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np


# ==========================================================================
# 1. Chunking
# ==========================================================================
def load_chunks(policies_dir):
    """
    One chunk per policy doc -- correct granularity for short SOPs. (If a doc
    grows past ~180 words, split it here by section; over-chunking tiny docs
    just destroys context, so we don't.)
    Each chunk keeps `doc` (the citation) and `content` (what we index/embed;
    the title is prepended so retrieval has topic context).
    """
    chunks = []
    for path in sorted(Path(policies_dir).glob("*.md")):
        text = path.read_text().strip()
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else path.stem
        body = "\n".join(lines[1:]).strip()
        chunks.append({
            "chunk_id": path.stem,
            "doc": path.name,                 # <- citation the agent will show
            "title": title,
            "text": body,
            "content": f"{title}. {body}",    # <- what BM25/embeddings see
        })
    return chunks


# ==========================================================================
# 2. Sparse retrieval: BM25 (pure Python, no dependencies, fully offline)
# ==========================================================================
_TOKEN = re.compile(r"[a-z0-9]+")

def tokenize(s):
    return _TOKEN.findall(s.lower())


class BM25:
    def __init__(self, corpus, k1=1.5, b=0.75):
        self.docs = [tokenize(d) for d in corpus]
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / self.N
        df = Counter()
        for d in self.docs:
            for w in set(d):
                df[w] += 1
        self.idf = {w: math.log(1 + (self.N - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = tokenize(query)
        out = np.zeros(self.N)
        for j, d in enumerate(self.docs):
            tf = Counter(d)
            dl = len(d)
            s = 0.0
            for w in q:
                if w in tf:
                    s += self.idf.get(w, 0.0) * (tf[w] * (self.k1 + 1)) / (
                        tf[w] + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out[j] = s
        return out


# ==========================================================================
# 3. Dense retrieval: pluggable embedders
# ==========================================================================
class StubEmbedder:
    """Deterministic hash-seeded vectors. Offline wiring ONLY -- not semantic."""
    dim = 64

    def embed(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode()).hexdigest(), 16) % (2**32)
            out.append(np.random.default_rng(seed).standard_normal(self.dim))
        return np.array(out)


class LocalEmbedder:
    """No API key. `pip install sentence-transformers` then use this."""
    def __init__(self, model="sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(model)

    def embed(self, texts):
        return np.asarray(self.m.encode(list(texts), normalize_embeddings=True))


class ApiEmbedder:
    """Needs OPENAI_API_KEY. `pip install openai`."""
    def __init__(self, model="text-embedding-3-small"):
        from openai import OpenAI
        self.c = OpenAI()
        self.model = model

    def embed(self, texts):
        r = self.c.embeddings.create(model=self.model, input=list(texts))
        return np.array([d.embedding for d in r.data])


# ==========================================================================
# 4. Hybrid index: BM25 + dense, fused with Reciprocal Rank Fusion
# ==========================================================================
def _ranks(scores):
    """Map each item -> its 1-based rank (best score = rank 1)."""
    order = np.argsort(-scores)
    r = np.empty(len(scores), dtype=int)
    for rank, i in enumerate(order):
        r[i] = rank + 1
    return r


class PolicyIndex:
    def __init__(self, chunks, embedder):
        self.chunks = chunks
        self.bm25 = BM25([c["content"] for c in chunks])
        self.embedder = embedder
        emb = embedder.embed([c["content"] for c in chunks])
        self.emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)

    def _dense(self, query):
        q = self.embedder.embed([query])[0]
        q = q / (np.linalg.norm(q) + 1e-9)
        return self.emb @ q                      # cosine similarity

    def search(self, query, k=3, mode="hybrid", rrf_k=60):
        bm = self.bm25.scores(query)
        if mode == "bm25":
            fused = bm
        elif mode == "dense":
            fused = self._dense(query)
        else:  # hybrid via RRF -- rank-based, so no score normalisation needed
            rb, rd = _ranks(bm), _ranks(self._dense(query))
            fused = 1.0 / (rrf_k + rb) + 1.0 / (rrf_k + rd)
        top = np.argsort(-fused)[:k]
        return [{
            "doc": self.chunks[i]["doc"],        # citation
            "title": self.chunks[i]["title"],
            "text": self.chunks[i]["text"],
            "score": round(float(fused[i]), 4),
        } for i in top]


# ==========================================================================
# 5. The TOOL the agent calls
# ==========================================================================
_INDEX = None

def build_index(policies_dir="policies", embedder=None):
    """Call once at startup. Swap the embedder here to go live:
         build_index('policies', LocalEmbedder())   # or ApiEmbedder()
    """
    global _INDEX
    _INDEX = PolicyIndex(load_chunks(policies_dir), embedder or StubEmbedder())
    return _INDEX

def search_policy(query, k=3, mode="hybrid"):
    if _INDEX is None:
        build_index()
    return _INDEX.search(query, k=k, mode=mode)


# ==========================================================================
# 6. Offline self-test
#    BM25 is real here. Dense is stubbed (no network), so we report the
#    honest, runnable number: BM25 top-1 doc accuracy on a small query set.
# ==========================================================================
if __name__ == "__main__":
    policies = Path(__file__).parent / "policies"
    build_index(policies)

    # (query, expected governing doc)
    probes = [
        ("a captured transaction never got settled",        "05_unsettled_transactions.md"),
        ("two settlements for the same transaction",         "06_duplicate_settlements.md"),
        ("settled amount doesn't match even after fees",     "02_amount_tolerances.md"),
        ("settlement took a week, is that acceptable",       "07_settlement_timing.md"),
        ("settlement is refunded but ledger says captured",  "08_status_reconciliation.md"),
        ("when do I escalate a case to a human",             "09_escalation.md"),
    ]

    print("BM25 (real) top-1 retrieval:")
    hits = 0
    for q, want in probes:
        top = search_policy(q, k=1, mode="bm25")[0]["doc"]
        ok = (top == want)
        hits += ok
        print(f"  [{'OK ' if ok else 'MISS'}] {q!r} -> {top}")
    print(f"  top-1 accuracy: {hits}/{len(probes)}\n")

    print("Hybrid pipeline (dense = STUB, proves wiring) sample:")
    for r in search_policy("what happens if a settlement is late", k=2):
        print(f"  {r['doc']:32s} score={r['score']}  ({r['title']})")