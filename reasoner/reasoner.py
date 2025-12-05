# reasoner/reasoner.py
import json
import time
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from .schemas import ActionSchema
from . import config as rconfig  # we'll describe config below
from runner.logger import log

# Load prompt templates
PROMPT_PATH = "reasoner/prompts/action_prompt.txt"
FEW_SHOT_PATH = "reasoner/prompts/few_shot_examples.json"

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

with open(FEW_SHOT_PATH, "r", encoding="utf-8") as f:
    FEW_SHOT_EXAMPLES = json.load(f)

# Config (set via environment or default)
# rconfig should provide AZURE endpoint/key/deployment_name etc.
# Minimal expected config object:
# AZURE_OPENAI_BASE, AZURE_OPENAI_KEY, AZURE_DEPLOYMENT, AZURE_API_VERSION

def _build_system_prompt(goal: str, elements: List[Dict[str, Any]], last_actions: Optional[List[Dict]] = None) -> str:
    # Build the prompt string with few-shot examples + current context
    examples = []
    for ex in FEW_SHOT_EXAMPLES:
        examples.append({
            "goal": ex["goal"],
            "elements": ex["elements"],
            "result": ex["result"],
        })
    # Inline examples as JSON to the prompt for clarity
    prompt = PROMPT_TEMPLATE + "\n\n"
    # Add examples
    prompt += "Few-shot examples (do not output these as answer):\n"
    prompt += json.dumps(examples, indent=2)
    prompt += "\n\nCurrent context:\n"
    prompt += json.dumps({"goal": goal, "elements": elements, "last_actions": last_actions or []}, indent=2)
    prompt += "\n\nReturn the single JSON action now."
    return prompt

def _get_llm():
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=rconfig.AZURE_OPENAI_BASE,
            openai_api_key=rconfig.AZURE_OPENAI_KEY,
            deployment_name=rconfig.AZURE_DEPLOYMENT,
            api_version=getattr(rconfig, "AZURE_API_VERSION", "2023-10-01"),
            max_tokens=512,
            temperature=0.0  # deterministic
        )
        return llm
    except Exception as e:
        log("WARN", "reasoner_llm_init_failed", "Failed to init AzureChatOpenAI, using mock", error=str(e))
        
        class MockLLM:
            def __call__(self, messages):
                from langchain_core.messages import AIMessage
                # Return a dummy JSON response
                return AIMessage(content='{"action": "noop", "target": null, "value": null, "confidence": 1.0, "reason": "Mock LLM used due to missing credentials"}')
        
        return MockLLM()

class Reasoner:
    def __init__(self, model=None):
        self.llm = model or _get_llm()

    def plan_one(self, goal: str, elements: List[Dict[str, Any]], last_actions: Optional[List[Dict]] = None) -> ActionSchema:
        """
        Returns a validated ActionSchema object representing the next action.
        Raises ValueError if unable to produce valid action.
        """
        prompt = _build_system_prompt(goal, elements, last_actions)
        # Ask LLM
        log("INFO", "reasoner_request", "Sending prompt to LLM", goal=goal, elements_count=len(elements))
        start = time.time()
        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            content = resp.content.strip()
            log("DEBUG", "reasoner_raw", "LLM raw output", output=content)
        except Exception as e:
            log("ERROR", "reasoner_llm_error", "LLM call failed", error=str(e))
            raise

        # Try to parse JSON
        parsed = None
        try:
            parsed = json.loads(content)
        except Exception:
            # try extracting JSON from text (common safety)
            import re
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None

        if not parsed:
            # Retry once with stricter instruction
            log("WARN", "reasoner_parse_failed", "Parsing failed; retrying with strict JSON instruction")
            strict_prompt = prompt + "\n\nIMPORTANT: Return only the JSON object and nothing else."
            resp = self.llm([HumanMessage(content=strict_prompt)])
            content = resp.content.strip()
            try:
                parsed = json.loads(content)
            except Exception as e:
                log("ERROR", "reasoner_parse_retry_failed", "Retry parse failed", error=str(e), raw=content)
                raise ValueError("LLM did not return valid JSON")

        # Validate schema
        try:
            action = ActionSchema.parse_obj(parsed)
            log("INFO", "reasoner_valid", "Action validated", action=action.dict())
            return action
        except ValidationError as ve:
            log("ERROR", "reasoner_validation_failed", "Schema validation failed", errors=ve.errors(), parsed=parsed)
            # Last resort: return noop
            raise ValueError("LLM output failed schema validation")

