from __future__ import annotations
import asyncio, json, os, time, hashlib, logging, hmac
import re
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, TypedDict
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from app.policy_decisions import assess_policy, prepare_recommendation
from app.reranking import rerank_candidates
from app.observability import tag_current_span, valid_correlation_id, record_ai_provider_attempt
from app.agent_memory import build_memory_graph, scoped_thread_id, validate_session_id
from app.agent_tools import execute_tool
from app.agent_retention import AgentMemoryRetention

async def agent_memory_cleanup_loop(application: FastAPI, interval_seconds: int):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            removed = await application.state.agent_memory_retention.expire(
                application.state.agent_memory_graph.checkpointer
            )
            if removed:
                logger.info("Expired stale agent-memory threads", extra={"thread_count": removed})
        except Exception as exc:
            logger.warning("Agent-memory retention sweep failed", extra={"error_type": type(exc).__name__})

@asynccontextmanager
async def lifespan(application: FastAPI):
    backend = os.getenv("AGENT_MEMORY_BACKEND", "memory").lower()
    if os.getenv("APP_ENV") == "production" and backend != "postgres":
        raise RuntimeError("Production AI runtime requires PostgreSQL-backed agent memory")
    ttl_days = int(os.getenv("AGENT_MEMORY_TTL_DAYS", "30"))
    if not 1 <= ttl_days <= 365:
        raise RuntimeError("AGENT_MEMORY_TTL_DAYS must be between 1 and 365")
    interval_seconds = int(os.getenv("AGENT_MEMORY_CLEANUP_INTERVAL_SECONDS", "3600"))
    if not 60 <= interval_seconds <= 86400:
        raise RuntimeError("AGENT_MEMORY_CLEANUP_INTERVAL_SECONDS must be between 60 and 86400")
    cleanup_task = None
    retention_connection = None
    checkpoint_context = None
    if backend == "memory":
        saver = InMemorySaver()
        application.state._agent_memory_context = None
        retention = AgentMemoryRetention(ttl_days=ttl_days)
    elif backend == "postgres":
        try:
            import psycopg
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.conninfo import make_conninfo
            from psycopg.rows import dict_row
            secret = json.loads(os.environ["POSTGRES_MASTER_SECRET_JSON"]) if os.getenv("POSTGRES_MASTER_SECRET_JSON") else {}
            dsn = os.getenv("DATABASE_URL") or make_conninfo(
                host=secret.get("host", os.getenv("POSTGRES_HOST", "localhost")),
                port=secret.get("port", os.getenv("POSTGRES_PORT", "5432")),
                user=secret.get("username", os.getenv("POSTGRES_USER", "opsbridge")),
                password=secret.get("password", os.getenv("POSTGRES_PASSWORD", "opsbridge")),
                dbname=os.getenv("POSTGRES_DB", secret.get("dbname", "opsbridge")),
                sslmode="require" if os.getenv("APP_ENV") == "production" else "prefer",
            )
            checkpoint_context = AsyncPostgresSaver.from_conn_string(dsn)
            saver = await checkpoint_context.__aenter__()
            await saver.setup()
            application.state._agent_memory_context = checkpoint_context
            retention_connection = await psycopg.AsyncConnection.connect(
                dsn, autocommit=True, row_factory=dict_row
            )
            retention = AgentMemoryRetention(ttl_days=ttl_days, connection=retention_connection)
            await retention.initialize()
        except Exception as exc:
            if retention_connection is not None:
                await retention_connection.close()
            if checkpoint_context is not None:
                await checkpoint_context.__aexit__(type(exc), exc, exc.__traceback__)
            raise RuntimeError("PostgreSQL agent memory could not be initialized") from exc
    else:
        raise RuntimeError("AGENT_MEMORY_BACKEND must be 'memory' or 'postgres'")
    application.state.agent_memory_graph = build_memory_graph(saver)
    application.state.agent_memory_retention = retention
    try:
        if backend == "postgres":
            # Sweep at startup and then periodically; explicit per-thread deletion remains available.
            await retention.expire(saver)
            cleanup_task = asyncio.create_task(agent_memory_cleanup_loop(application, interval_seconds))
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        if retention_connection is not None:
            await retention_connection.close()
        context = getattr(application.state, "_agent_memory_context", None)
        if context is not None:
            await context.__aexit__(None, None, None)

app = FastAPI(title="OpsBridge AI Runtime", version="1.0.0", lifespan=lifespan)
logger=logging.getLogger('opsbridge.ai')
usage_totals={"requests":0,"attempts":0,"failures":0,"fallbacks":0,"input_tokens":0,"output_tokens":0,"estimated_cost_usd":0.0,"providers":{}}
AI_PROVIDER_ATTEMPTS=Counter("opsbridge_ai_provider_attempts_total","LLM provider attempts by outcome",["provider","outcome"])
AI_PROVIDER_LATENCY=Histogram("opsbridge_ai_provider_attempt_duration_seconds","LLM provider attempt latency",["provider"],buckets=(0.05,0.1,0.25,0.5,1,2,5,10,30,60))
AI_PROVIDER_TOKENS=Counter("opsbridge_ai_provider_tokens_total","Provider-reported LLM tokens",["provider","direction"])
AI_PROVIDER_COST=Counter("opsbridge_ai_provider_estimated_cost_usd_total","Estimated provider cost based on configured token rates",["provider"])
AI_PROVIDER_FALLBACKS=Counter("opsbridge_ai_provider_fallback_successes_total","Successful requests served by a configured fallback",["provider"])

@app.middleware('http')
async def require_trusted_service(request, call_next):
    correlation_id=request.headers.get('X-Correlation-Id','')
    if valid_correlation_id(correlation_id):
        tag_current_span(correlation_id)
    if os.getenv('APP_ENV') == 'production' and request.url.path not in {'/health','/metrics'}:
        expected=os.getenv('INTERNAL_SERVICE_TOKEN','')
        supplied=request.headers.get('X-Internal-Service-Token','')
        if not expected or not hmac.compare_digest(supplied,expected):
            response=JSONResponse(status_code=401,content={'detail':'Trusted service context required.'})
        else:
            response=await call_next(request)
    else:
        response=await call_next(request)
    if valid_correlation_id(correlation_id):
        response.headers['X-Correlation-Id']=correlation_id
    return response

class ExtractRequest(BaseModel):
    document_text: str = Field(min_length=1, max_length=100_000)
    document_type: str = "identity"
    expected_fields: list[str] = Field(default_factory=lambda: ["full_name", "document_number", "expiry_date"])

class RecommendationRequest(BaseModel):
    case_id: str
    worker_profile: dict[str, Any]
    extracted_documents: list[dict[str, Any]] = Field(default_factory=list)
    policy_text: str = "Verify required identity and work eligibility documents. Escalate low confidence and conflicting data to an authorized reviewer."

class AgentState(TypedDict, total=False):
    request: dict[str, Any]
    assessment: dict[str, Any]
    recommendation: dict[str, Any]

def parse_json(text: str):
    cleaned=text.strip().removeprefix('```json').removesuffix('```').strip()
    return json.loads(cleaned)

async def invoke_provider(provider: str, system: str, user: str) -> tuple[dict[str, Any], str, int, int]:
    """Invoke one configured provider; split out to make failures deterministic in tests."""
    if provider=='openai':
        from openai import AsyncOpenAI
        model=os.getenv('OPENAI_MODEL','gpt-4o-mini')
        response=await AsyncOpenAI().chat.completions.create(model=model,response_format={'type':'json_object'},messages=[{'role':'system','content':system},{'role':'user','content':user}])
        return parse_json(response.choices[0].message.content or '{}'),model,response.usage.prompt_tokens if response.usage else 0,response.usage.completion_tokens if response.usage else 0
    if provider=='gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        model=os.getenv('GEMINI_MODEL','gemini-2.0-flash')
        reply=await ChatGoogleGenerativeAI(model=model,temperature=0).ainvoke(f'{system}\nReturn only JSON.\n{user}')
        result=parse_json(str(reply.content));meta=reply.usage_metadata or {}
        return result,model,meta.get('input_tokens',0),meta.get('output_tokens',0)
    if provider=='anthropic':
        from anthropic import AsyncAnthropic
        model=os.getenv('ANTHROPIC_MODEL','claude-3-5-haiku-latest')
        reply=await AsyncAnthropic().messages.create(model=model,max_tokens=1600,system=system,messages=[{'role':'user','content':user+'\nReturn only a JSON object.'}])
        result=parse_json(''.join(block.text for block in reply.content if getattr(block,'type',None)=='text'))
        return result,model,reply.usage.input_tokens,reply.usage.output_tokens
    raise ValueError(f'Unsupported LLM provider: {provider}')

def provider_cost_per_1k(provider: str, direction: str) -> float:
    provider_key=f"{provider.upper()}_COST_PER_1K_{direction.upper()}_USD"
    shared_key=f"LLM_COST_PER_1K_{direction.upper()}_USD"
    return float(os.getenv(provider_key,os.getenv(shared_key,"0")))

async def provider_json(
    system: str,
    user: str,
    *,
    tenant_id: str = "",
    correlation_id: str = "",
) -> dict[str, Any]:
    preferred=os.getenv('DEFAULT_LLM_PROVIDER','mock').lower()
    order=[preferred]+[p.strip().lower() for p in os.getenv('LLM_FALLBACK_PROVIDERS','openai,gemini,anthropic').split(',') if p.strip() and p.strip().lower()!=preferred]
    if preferred=='mock':return {"fields":{},"confidence":0.0,"warnings":["LLM provider is not configured; no AI extraction was performed."],"provider":"mock","_usage":{"provider":"mock","model":"none","latency_ms":0,"input_tokens":0,"output_tokens":0,"estimated_cost_usd":0.0,"fallback_used":False,"attempts":[]}}
    request_started=time.perf_counter()
    attempt_results=[]
    failure_attribution=[]
    attempted=0
    for order_index,provider in enumerate(order):
        key={'openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY','anthropic':'ANTHROPIC_API_KEY'}.get(provider)
        if not key:
            attempt_results.append({"provider":provider,"outcome":"skipped","reason":"unsupported_provider"})
            continue
        if not os.getenv(key):
            attempt_results.append({"provider":provider,"outcome":"skipped","reason":"missing_credentials"})
            continue
        attempted+=1
        usage_totals["attempts"]+=1
        stats=usage_totals["providers"].setdefault(provider,{"attempts":0,"successes":0,"failures":0,"fallback_successes":0,"input_tokens":0,"output_tokens":0,"estimated_cost_usd":0.0})
        stats["attempts"]+=1
        started=time.perf_counter()
        try:
            result,model,input_tokens,output_tokens=await invoke_provider(provider,system,user)
            elapsed=round((time.perf_counter()-started)*1000);rate_in=provider_cost_per_1k(provider,"input");rate_out=provider_cost_per_1k(provider,"output");cost=input_tokens*rate_in/1000+output_tokens*rate_out/1000
            fallback_used=order_index>0 or len(attempt_results)>0
            attempt_record={"provider":provider,"outcome":"success","latency_ms":elapsed}
            attempt_results.append(attempt_record)
            record_ai_provider_attempt(provider,"success",attempted,elapsed,fallback_used=fallback_used)
            AI_PROVIDER_ATTEMPTS.labels(provider=provider,outcome="success").inc()
            AI_PROVIDER_LATENCY.labels(provider=provider).observe(elapsed/1000)
            AI_PROVIDER_TOKENS.labels(provider=provider,direction="input").inc(input_tokens)
            AI_PROVIDER_TOKENS.labels(provider=provider,direction="output").inc(output_tokens)
            AI_PROVIDER_COST.labels(provider=provider).inc(cost)
            usage_totals['requests']+=1;usage_totals['input_tokens']+=input_tokens;usage_totals['output_tokens']+=output_tokens;usage_totals['estimated_cost_usd']+=cost
            stats["successes"]+=1;stats["input_tokens"]+=input_tokens;stats["output_tokens"]+=output_tokens;stats["estimated_cost_usd"]+=cost
            if fallback_used:
                usage_totals["fallbacks"]+=1
                stats["fallback_successes"]+=1
                AI_PROVIDER_FALLBACKS.labels(provider=provider).inc()
            result['_usage']={'provider':provider,'model':model,'latency_ms':round((time.perf_counter()-request_started)*1000),'input_tokens':input_tokens,'output_tokens':output_tokens,'cost_per_1k_input_usd':rate_in,'cost_per_1k_output_usd':rate_out,'estimated_cost_usd':round(cost,8),'fallback_used':fallback_used,'attempts':attempt_results,'failure_attribution':failure_attribution};return result
        except Exception as exc:
            elapsed=round((time.perf_counter()-started)*1000)
            error_type=type(exc).__name__[:80]
            usage_totals["failures"]+=1;stats["failures"]+=1
            attempt_results.append({"provider":provider,"outcome":"failure","latency_ms":elapsed,"error_type":error_type})
            failure_attribution.append({"provider":provider,"error_type":error_type})
            fallback_used=order_index>0
            record_ai_provider_attempt(provider,"failure",attempted,elapsed,error_type=error_type,fallback_used=fallback_used)
            AI_PROVIDER_ATTEMPTS.labels(provider=provider,outcome="failure").inc()
            AI_PROVIDER_LATENCY.labels(provider=provider).observe(elapsed/1000)
            logger.warning('LLM provider request failed; trying configured fallback',extra={'provider':provider,'error_type':error_type,'correlation_id':correlation_id[:100]})
    return {"fields":{},"confidence":0.0,"warnings":["No configured LLM provider was available; manual review is required."],"provider":"unavailable","_usage":{"provider":"unavailable","model":"none","latency_ms":round((time.perf_counter()-request_started)*1000),'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0.0,'fallback_used':False,'attempts':attempt_results,'failure_attribution':failure_attribution}}

def database_connection():
    import psycopg
    from pgvector.psycopg import register_vector
    secret=json.loads(os.environ['POSTGRES_MASTER_SECRET_JSON']) if os.getenv('POSTGRES_MASTER_SECRET_JSON') else {}
    if os.getenv('DATABASE_URL'):
        conn=psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=4)
    else:
        conn=psycopg.connect(host=secret.get('host',os.getenv('POSTGRES_HOST','localhost')),port=secret.get('port',os.getenv('POSTGRES_PORT','5432')),user=secret.get('username',os.getenv('POSTGRES_USER','opsbridge')),password=secret.get('password',os.getenv('POSTGRES_PASSWORD','opsbridge')),dbname=os.getenv('POSTGRES_DB',secret.get('dbname','opsbridge')),connect_timeout=4,sslmode='require' if os.getenv('APP_ENV')=='production' else 'prefer')
    conn.execute('CREATE EXTENSION IF NOT EXISTS vector');conn.commit();register_vector(conn)
    conn.execute('CREATE TABLE IF NOT EXISTS policy_chunks (id uuid PRIMARY KEY, tenant_id varchar(100) NOT NULL, title text NOT NULL, chunk text NOT NULL, embedding vector(1536), created_at timestamptz NOT NULL DEFAULT now())')
    conn.execute('CREATE INDEX IF NOT EXISTS policy_chunks_tenant_idx ON policy_chunks(tenant_id)')
    conn.commit();return conn

async def embedding_for(text: str):
    if not os.getenv('OPENAI_API_KEY'):return None
    from openai import AsyncOpenAI
    result=await AsyncOpenAI().embeddings.create(model=os.getenv('OPENAI_EMBEDDING_MODEL','text-embedding-3-small'),input=text[:8000])
    return result.data[0].embedding

@lru_cache(maxsize=1)
def cross_encoder_reranker():
    """Load the optional model once; absent dependency/model means RRF fallback."""
    if os.getenv('RAG_RERANKER_ENABLED','false').lower() not in {'1','true','yes','on'}:
        return None
    try:
        from sentence_transformers import CrossEncoder
        model=os.getenv('RAG_RERANKER_MODEL','cross-encoder/ms-marco-MiniLM-L6-v2')
        return CrossEncoder(model, device=os.getenv('RAG_RERANKER_DEVICE','cpu'))
    except Exception as exc:
        logger.warning('Cross-encoder unavailable; using hybrid retrieval order',extra={'error_type':type(exc).__name__})
        return None

def chunks_for(text: str, limit: int=900):
    paragraphs=[p.strip() for p in text.splitlines() if p.strip()]
    chunks=[];current=''
    for paragraph in paragraphs:
        while len(paragraph)>limit:
            if current:chunks.append(current);current=''
            chunks.append(paragraph[:limit]);paragraph=paragraph[limit:]
        if len(current)+len(paragraph)+1>limit and current:chunks.append(current);current=''
        current=(current+'\n'+paragraph).strip()
    if current:chunks.append(current)
    return chunks[:100]

async def retrieve_policy(query: str, tenant_id: str):
    try:
        from pgvector.psycopg import Vector
        conn=database_connection()
        embedding=await embedding_for(query)
        lexical=conn.execute("SELECT title,chunk FROM policy_chunks WHERE tenant_id=%s AND to_tsvector('english',title||' '||chunk) @@ websearch_to_tsquery('english',%s) ORDER BY ts_rank(to_tsvector('english',title||' '||chunk),websearch_to_tsquery('english',%s)) DESC LIMIT 10",(tenant_id,query,query)).fetchall()
        ranked={}
        # Reciprocal-rank fusion combines lexical and semantic orderings without
        # pretending their raw scores share the same scale.
        for rank,row in enumerate(lexical,1):
            key=(row[0],row[1]);ranked.setdefault(key,0.0);ranked[key]+=1/(60+rank)
        if embedding is not None:
            semantic=conn.execute('SELECT title,chunk FROM policy_chunks WHERE tenant_id=%s AND embedding IS NOT NULL ORDER BY embedding <=> %s LIMIT 10',(tenant_id,Vector(embedding))).fetchall()
            for rank,row in enumerate(semantic,1):
                key=(row[0],row[1]);ranked.setdefault(key,0.0);ranked[key]+=1/(60+rank)
        conn.close()
        # Retrieval SQL is tenant-filtered before any model receives document
        # text. Rerank a bounded fused candidate set, then return the best five.
        candidates=[{'title':title,'content':chunk,'retrievalScore':round(score,6)} for (title,chunk),score in sorted(ranked.items(),key=lambda item:item[1],reverse=True)[:20]]
        model=cross_encoder_reranker()
        if model is not None and candidates:
            try:
                candidates=await asyncio.to_thread(rerank_candidates,query,candidates,model)
            except Exception as exc:
                logger.warning('Cross-encoder scoring failed; using hybrid retrieval order',extra={'error_type':type(exc).__name__})
        return candidates[:5]
    except Exception:
        return []

@app.get("/health")
async def health(): return {"status":"ok","service":"ai-runtime","provider":os.getenv("DEFAULT_LLM_PROVIDER","mock")}

@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/extract")
async def extract(req: ExtractRequest, x_tenant_id: str=Header(...), x_correlation_id: str=Header(default="")):
    if not x_tenant_id or len(x_tenant_id)>100: raise HTTPException(400,"A valid tenant context is required.")
    result=await provider_json("Extract only information explicitly present in the supplied document. Do not infer missing values. Return JSON keys fields, confidence (0..1), warnings, evidence. Never output a final eligibility decision.",json.dumps({"document_type":req.document_type,"expected_fields":req.expected_fields,"document_text":req.document_text}),tenant_id=x_tenant_id,correlation_id=x_correlation_id if valid_correlation_id(x_correlation_id) else "")
    result.setdefault("fields",{}); result.setdefault("confidence",0.0); result.setdefault("warnings",[]); result["human_review_required"]=float(result.get("confidence",0))<float(os.getenv("AI_REVIEW_CONFIDENCE_THRESHOLD","0.85"))
    return result

builder=StateGraph(AgentState); builder.add_node("assess_policy",assess_policy); builder.add_node("prepare_recommendation",prepare_recommendation); builder.add_edge(START,"assess_policy"); builder.add_edge("assess_policy","prepare_recommendation"); builder.add_edge("prepare_recommendation",END); onboarding_graph=builder.compile()

@app.post("/v1/recommend")
async def recommend(req: RecommendationRequest, x_tenant_id: str=Header(...)):
    context=await retrieve_policy(req.policy_text,x_tenant_id)
    request=req.model_dump()
    if context:request['policy_text']='\n\n'.join(item['content'] for item in context)
    result=await onboarding_graph.ainvoke({"request":request}); return {"case_id":req.case_id,"tenant_id":x_tenant_id,"policy_sources":[item['title'] for item in context],**result["recommendation"]}

class RedactRequest(BaseModel): text: str=Field(min_length=1,max_length=100_000)
@app.post('/v1/security/redact')
async def redact(req:RedactRequest,x_tenant_id:str=Header(...)):
    patterns={'email':r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b','india_pan':r'\b[A-Z]{5}[0-9]{4}[A-Z]\b','aadhaar_like':r'\b(?:\d{4}[ -]?){2}\d{4}\b','phone_like':r'(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)'}
    found=[];redacted=req.text
    for kind,pattern in patterns.items():
        matches=list(re.finditer(pattern,redacted))
        for match in reversed(matches):redacted=redacted[:match.start()]+'[REDACTED:'+kind+']'+redacted[match.end():]
        found.extend({'type':kind,'start':m.start(),'end':m.end()} for m in matches)
    return {'tenant_id':x_tenant_id,'redacted_text':redacted,'detections':found,'count':len(found),'policy':'Redaction is pattern-based and may miss sensitive data; review before external sharing.'}

class VoiceSummaryRequest(BaseModel): transcript: str=Field(min_length=1,max_length=50_000); language: str='en'
@app.post('/v1/voice/summarize')
async def summarize_voice(req:VoiceSummaryRequest,x_tenant_id:str=Header(...),x_correlation_id:str=Header(default="")):
    response=await provider_json('Summarize a business intake call. Extract only statements explicitly present. Return JSON keys summary, requested_actions (array), caller_preferences (array), unresolved_questions (array), suggested_route. Never infer protected or sensitive traits and never make an eligibility decision.',json.dumps({'language':req.language,'transcript':req.transcript}),tenant_id=x_tenant_id,correlation_id=x_correlation_id if valid_correlation_id(x_correlation_id) else "")
    return {'tenant_id':x_tenant_id,'summary':response,'human_review_required':True,'transcript_persisted':False}

@app.post("/v1/evaluate")
async def evaluate(payload: dict[str,Any], x_tenant_id: str=Header(...), x_correlation_id: str=Header(default="")):
    examples=payload.get("examples",[]); results=[]
    for row in examples:
        answer=await provider_json("Evaluate the supplied expected behavior against the model response. Output JSON with pass boolean and concise reason.",json.dumps(row),tenant_id=x_tenant_id,correlation_id=x_correlation_id if valid_correlation_id(x_correlation_id) else ""); results.append(answer)
    passed=sum(1 for row in results if row.get("pass") is True)
    return {"tenant_id":x_tenant_id,"count":len(results),"passed":passed,"pass_rate":passed/len(results) if results else 0,"results":results}

class PolicyIndexRequest(BaseModel): title: str=Field(min_length=1,max_length=240); content: str=Field(min_length=1,max_length=100_000)
@app.post('/v1/knowledge/policies')
async def index_policy(req:PolicyIndexRequest,x_tenant_id:str=Header(...)):
    pieces=chunks_for(req.content)
    if not pieces:raise HTTPException(400,'Policy text did not contain indexable content.')
    try:
        from pgvector.psycopg import Vector
        conn=database_connection()
        vectors=[]
        for piece in pieces:
            vector=await embedding_for(piece);vectors.append(vector)
        with conn.transaction():
            conn.execute('DELETE FROM policy_chunks WHERE tenant_id=%s AND title=%s',(x_tenant_id,req.title))
            for piece,vector in zip(pieces,vectors):conn.execute('INSERT INTO policy_chunks(id,tenant_id,title,chunk,embedding) VALUES(%s,%s,%s,%s,%s)',(str(__import__('uuid').uuid4()),x_tenant_id,req.title,piece,Vector(vector) if vector else None))
        conn.close();return {'title':req.title,'chunksIndexed':len(pieces),'embeddingEnabled':all(v is not None for v in vectors)}
    except Exception as exc:raise HTTPException(503,'Policy index is unavailable. Start PostgreSQL with the pgvector image.') from exc

@app.post('/v1/knowledge/search')
async def search_policy(payload:dict[str,Any],x_tenant_id:str=Header(...)):
    query=str(payload.get('query','')).strip()
    if not query:raise HTTPException(400,'query is required.')
    return {'items':await retrieve_policy(query,x_tenant_id)}

class AgentExecutionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    plan: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    tool_name: str | None = Field(default=None, max_length=80)
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    requires_external_action: bool = False
    approved: bool = False

    @field_validator("plan")
    @classmethod
    def limit_plan_size(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(json.dumps(value, ensure_ascii=False)) > 8000:
            raise ValueError("plan must be no larger than 8000 characters when serialized")
        return value

    @field_validator("tool_arguments")
    @classmethod
    def limit_tool_argument_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False)) > 2000:
            raise ValueError("tool_arguments must be no larger than 2000 characters when serialized")
        return value

@app.post("/v1/agents/execute")
async def execute_agent(
    payload: AgentExecutionRequest,
    x_tenant_id: str = Header(...),
    x_actor_id: str = Header(default="service"),
    x_correlation_id: str = Header(default=""),
):
    try:
        thread_id = scoped_thread_id(x_tenant_id, x_actor_id, payload.session_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    status = "awaiting_human_approval" if payload.requires_external_action and not payload.approved else "accepted"
    tool_result = None
    if payload.tool_name is not None:
        tool_result = await execute_tool(
            payload.tool_name,
            payload.tool_arguments,
            tenant_id=x_tenant_id,
            actor_id=x_actor_id,
            correlation_id=x_correlation_id if valid_correlation_id(x_correlation_id) else "",
        )
    config = {"configurable": {"thread_id": thread_id}}
    await app.state.agent_memory_retention.touch(thread_id)
    result = await app.state.agent_memory_graph.ainvoke({
        "messages": [{"role": "user", "content": payload.message}],
        "last_plan": payload.plan,
        "last_status": status,
        "last_tool_result": tool_result,
    }, config=config)
    return {
        "status": status,
        "tenant_id": x_tenant_id,
        "session_id": payload.session_id,
        "messages": result.get("messages", [])[-20:],
        "plan": payload.plan,
        "tool_name": payload.tool_name,
        "tool_result": tool_result,
        "tool_executed": tool_result is not None,
        "executed": False,
        "message": "Only allow-listed read-only tools are available; no external action is executed by this runtime.",
    }

@app.get("/v1/agents/threads/{session_id}")
async def get_agent_thread(
    session_id: str,
    x_tenant_id: str = Header(...),
    x_actor_id: str = Header(default="service"),
):
    try:
        thread_id = scoped_thread_id(x_tenant_id, x_actor_id, session_id)
        validate_session_id(session_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    state = await app.state.agent_memory_graph.aget_state({"configurable": {"thread_id": thread_id}})
    if not state.values:
        raise HTTPException(404, "Agent session not found.")
    await app.state.agent_memory_retention.touch(thread_id)
    return {"session_id": session_id, "messages": state.values.get("messages", [])[-20:], "plan": state.values.get("last_plan", []), "status": state.values.get("last_status", "accepted"), "tool_result": state.values.get("last_tool_result")}

@app.delete("/v1/agents/threads/{session_id}", status_code=204)
async def delete_agent_thread(
    session_id: str,
    x_tenant_id: str = Header(...),
    x_actor_id: str = Header(default="service"),
):
    try:
        thread_id = scoped_thread_id(x_tenant_id, x_actor_id, session_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await app.state.agent_memory_graph.checkpointer.adelete_thread(thread_id)
    await app.state.agent_memory_retention.forget(thread_id)
