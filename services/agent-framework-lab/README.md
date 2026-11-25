# Agent framework comparison lab

Optional FastAPI service for comparing AutoGen AgentChat sequential reviewers with a Semantic Kernel ChatCompletionAgent. Both endpoints accept synthetic text, have no action tools, and explicitly return advisory output for a human. Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL` before calling the endpoints. They are not part of the main onboarding workflow and should not receive applicant documents.

The AutoGen example follows the official AgentChat model-client and `AssistantAgent.run` flow. The Semantic Kernel example uses `ChatCompletionAgent.get_response`. No endpoint sends messages, changes case records, or initiates provider calls. Source has not been executed in this turn.
