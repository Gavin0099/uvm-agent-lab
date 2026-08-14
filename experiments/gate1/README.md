# Gate 1: Spec / Retrieval Accuracy

## Objective
Evaluate whether `spec-reference-kit` (governed knowledge layer) outperforms baseline retrieval architectures (BM25, Vector RAG, Hybrid) in precision and authority adherence.

## Target Metrics
- Recall@1 >= 95%
- Recall@3 = 100%
- Wrong-version rate = 0%
- Wrong-authority rate = 0%
- Wrong-customer leak rate = 0%

## Verification Command
```bash
python retrieval/evaluator.py
```
