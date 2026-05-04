from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from openai import OpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are UBID Assistant for Karnataka business identity resolution. "
    "You help users understand registrations, department links, UBID status, duplicate record risks, and next steps. "
    "You must not claim official legal finality. Use only the provided deterministic data and rules. "
    "Return concise helpful guidance and structured JSON."
)


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_configured(self) -> bool:
        return self.settings.openrouter_configured

    def render_guidance(self, message: str, structured_output: dict[str, Any]) -> tuple[str, bool]:
        if not self.is_configured():
            return self._fallback_reply(structured_output), False
        try:
            client = OpenAI(
                api_key=self.settings.openrouter_api_key,
                base_url=self.settings.openrouter_base_url,
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds),
            )
            response = client.chat.completions.create(
                model=self.settings.openrouter_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_message": message,
                                "deterministic_payload": structured_output,
                                "instructions": "Return a JSON object with keys reply and structured_output. Do not invent facts.",
                            }
                        ),
                    },
                ],
                temperature=0.1,
            )
            content = response.choices[0].message.content or ""
            parsed = self._extract_json(content)
            if not isinstance(parsed, dict) or "reply" not in parsed:
                raise ValueError("Invalid JSON payload returned by model")
            reply = str(parsed.get("reply", "")).strip() or self._fallback_reply(structured_output)
            return reply, True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("OpenRouter call failed, using fallback: %s", exc)
            return self._fallback_reply(structured_output), False

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("{"):
            return json.loads(content)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")
        return json.loads(match.group(0))

    @staticmethod
    def _fallback_reply(structured_output: dict[str, Any]) -> str:
        summary = structured_output.get("summary")
        if summary:
            return str(summary)
        if "recommended_departments" in structured_output:
            departments = ", ".join(structured_output.get("recommended_departments", []))
            return f"Recommended departments: {departments or 'none identified yet'}."
        if "candidate_matches" in structured_output:
            count = len(structured_output.get("candidate_matches", []))
            return f"Entity resolution completed with {count} candidate matches."
        if "risk_score" in structured_output:
            return f"Calculated risk score is {structured_output['risk_score']} ({structured_output.get('risk_level', 'UNKNOWN')})."
        return "Deterministic guidance is available in structured_output."
