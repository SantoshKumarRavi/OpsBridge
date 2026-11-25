"""Optional AutoGen and Semantic Kernel comparison with no executable tools."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="OpsBridge Agent Framework Lab", version="1.0.0")


class ReviewInput(BaseModel):
    scenario: str = Field(min_length=1, max_length=5000, description="Synthetic workflow scenario only")


def require_openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise HTTPException(503, "Set OPENAI_API_KEY to run this optional agent-framework lab.")
    return key


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-framework-lab", "sideEffects": False}


@app.post("/lab/v1/autogen/review")
async def autogen_review(request: ReviewInput):
    require_openai_key()
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    client = OpenAIChatCompletionClient(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    researcher = AssistantAgent(
        "evidence_analyst", client,
        system_message="Analyze this synthetic workflow scenario. List only stated facts, unknowns, and a safe next step. Do not make employment or regulatory decisions.",
    )
    reviewer = AssistantAgent(
        "human_review_planner", client,
        system_message="Review the analyst notes for unsupported assumptions. Return risks, evidence a person should inspect, and a suggested human review route. Do not execute tools or decide eligibility.",
    )
    try:
        analysis = await researcher.run(task=request.scenario)
        notes = str(analysis.messages[-1].content)
        review = await reviewer.run(task=f"Scenario: {request.scenario}\nAnalyst notes: {notes}")
        return {"framework": "autogen-agentchat", "analysis": notes, "review": str(review.messages[-1].content), "humanDecisionRequired": True, "toolsExecuted": False}
    finally:
        await client.close()


@app.post("/lab/v1/semantic-kernel/review")
async def semantic_kernel_review(request: ReviewInput):
    key = require_openai_key()
    from semantic_kernel.agents import ChatCompletionAgent
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

    service = OpenAIChatCompletion(ai_model_id=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), api_key=key)
    agent = ChatCompletionAgent(
        service=service,
        name="OpsBridgeWorkflowAssistant",
        instructions="Summarize this synthetic operations scenario. Separate facts from unknowns, identify policy evidence a reviewer should inspect, and recommend a human-owned next step. Never make a hiring, KYC, medical, or regulatory decision. Never execute external actions.",
    )
    response = await agent.get_response(messages=request.scenario)
    return {"framework": "semantic-kernel", "summary": str(response.content), "humanDecisionRequired": True, "toolsExecuted": False}
