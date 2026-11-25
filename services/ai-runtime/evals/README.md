# Synthetic RAG retrieval evaluation

`rag-golden-set.json` is a small synthetic relevance set. The indexing script `scripts/index-sample-policy.py` indexes every Markdown policy in `policies/`; set `AI_RUNTIME_URL` to index through the AI runtime directly, or leave it unset to use the API gateway. When embeddings are enabled, the runtime combines tenant-filtered PostgreSQL full-text and pgvector rankings with reciprocal-rank fusion. Without an embedding provider key, it falls back to PostgreSQL full-text search. An optional cross-encoder can rerank the top 20 hybrid candidates before returning the top five. Candidate retrieval applies the tenant filter before document text is sent to the model.

To try the reranker in Compose, set `AI_INSTALL_RERANKER=true` and `RAG_RERANKER_ENABLED=true` in `.env`, then rebuild `ai-runtime`. The Sentence Transformers dependency and model download make this image and first model load substantially larger; the default remains disabled and the standard RRF ordering remains the fallback if model loading or scoring fails. `RAG_RERANKER_MODEL` selects a compatible Sentence Transformers CrossEncoder model and `RAG_RERANKER_DEVICE` defaults to CPU. Compare the same labeled queries with reranking on/off before treating it as a quality improvement; reranking adds inference latency and this small synthetic set is not a validated benchmark.

Start PostgreSQL/pgvector and the AI runtime, index the sample policy documents, then run `python scripts/evaluate_rag.py`. The harness reports Recall@5, Precision@5, mean reciprocal rank, p95 latency, whether the reranker actually scored any query, and a cross-tenant isolation probe. It exits nonzero when configured thresholds fail. Set `MIN_RECALL_AT_5`, `MIN_MRR`, `MAX_P95_SECONDS`, `AI_RUNTIME_URL`, and `OPSBRIDGE_TENANT_ID` to adapt it to an isolated environment. Set `RAG_EVAL_OUTPUT_PATH` to save a machine-readable report; GitHub Actions uploads this report and adds a short summary. To compare modes, run the same dataset once with reranking disabled and once enabled, then compare recall/MRR and latency reports. The `rag-retrieval-evaluation` GitHub Actions job runs the baseline against PostgreSQL/pgvector without calling an external LLM or embedding provider.

This small golden set is a starter, not a validated benchmark. Review relevance labels with a human, grow the dataset with difficult/ambiguous questions, track prompt/model versions for generative evaluations, and do not use these scores as evidence of hiring or compliance accuracy. The evaluation is wired into CI but has not yet had a hosted run; local execution requires Docker and Docker is not available in the current environment.

## Compare live LLM providers

The optional `provider_reliability.py` harness sends three synthetic extraction cases to each configured OpenAI, Gemini, and Anthropic provider. It reports exact-field accuracy, completion/fallback rates, p95 latency, token counts, configured-rate cost estimates, failed attempts, and failure types. The report includes the selected model name and synthetic dataset version.

Copy `.env.example` to `.env`, add only the provider keys you intend to compare, and set realistic provider-specific `OPENAI_`, `GEMINI_`, and `ANTHROPIC_COST_PER_1K_{INPUT,OUTPUT}_USD` rates for the selected models. If a provider-specific rate is unset, the runtime uses the shared `LLM_COST_PER_1K_*` fallback rate. Then run:

```powershell
docker compose -f infra/docker-compose.yml --profile ai-evaluation run --rm ai-provider-evaluation
```

The report is written to `artifacts/ai-provider-reliability.json`. This command makes live model API calls and can incur provider charges. Run it deliberately after configuring keys and rates. The three-case synthetic set is an engineering smoke benchmark, not a statistically reliable or human-validated model ranking; compare multiple runs and expand/review the golden set before drawing quality conclusions.
