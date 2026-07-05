import json
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        text = user_prompt.lower()
        if "route" in system_prompt.lower():
            if any(term in text for term in ["cancel", "refund", "payment", "billing", "invoice"]):
                return {
                    "domain": "payments_cancellations",
                    "priority": "normal",
                    "confidence": 0.92,
                    "reasoning": "The message is about billing, payments, or cancellation.",
                }
            if any(term in text for term in ["bug", "error", "crash", "broken"]):
                return {"domain": "bugs", "priority": "high", "confidence": 0.9, "reasoning": "The message reports a defect."}
            if any(term in text for term in ["down", "slow", "outage", "service"]):
                return {"domain": "service_issues", "priority": "high", "confidence": 0.88, "reasoning": "The message reports a service issue."}
            return {"domain": "general_support", "priority": "normal", "confidence": 0.8, "reasoning": "No specialist domain matched strongly."}
        return {
            "body": (
                "Hi,\n\nThanks for contacting support. I reviewed your request and we can help with this. "
                "I have recorded the details and the appropriate support team will take the next step.\n\nBest,\nCustomer Support"
            ),
            "confidence": 0.86,
            "needs_review": False,
            "reasoning": "The reply is generic and safe for the detected support request.",
        }


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

