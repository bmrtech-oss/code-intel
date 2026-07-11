import json
import os
import re
import httpx
import logging
from abc import ABC, abstractmethod
from ollama import AsyncClient
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ..settings import (
    LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE,
    LLM_API_KEY, LLM_BASE_URL, OLLAMA_URL
)

PROMPTS_DIR = os.getenv("PROMPTS_DIR", "prompts")

class Task(BaseModel):
    text: str
    traceability: List[str]

class RequirementResponse(BaseModel):
    epic: str
    feature: str
    user_story: str
    acceptance_criteria: List[str]
    tasks: List[Task]

class ModelHandler(ABC):
    @abstractmethod
    def build_prompt(self, symbols: List[Dict], calls: List[Dict]) -> str:
        pass

    @abstractmethod
    def parse_response(self, raw_response: str) -> Dict[str, Any]:
        pass

class FileBasedHandler(ModelHandler):
    def __init__(self, prompt_file: str):
        prompt_path = os.path.join(PROMPTS_DIR, prompt_file)
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r') as f:
                self.template = f.read()
        else:
            logging.warning(f"Prompt file {prompt_path} not found. Using default template.")
            self.template = "Analyze the following code and generate requirements in JSON format.\nSymbols: {{symbols}}\nCalls: {{calls}}"

    def build_prompt(self, symbols, calls):
        symbols_str = json.dumps(symbols, indent=2) if symbols else "No symbols found."
        calls_str = json.dumps(calls, indent=2) if calls else "No calls found."
        return self.template.replace('{{symbols}}', symbols_str).replace('{{calls}}', calls_str)

    def parse_response(self, raw_response: str) -> Dict[str, Any]:
        cleaned = raw_response.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            
            logging.warning(f"JSON parsing failed. Trying json_repair. Raw: {raw_response[:100]}...")
            try:
                from json_repair import repair_json
                repaired = repair_json(cleaned)
                return json.loads(repaired)
            except Exception as e:
                logging.error(f"json_repair also failed: {e}")
            
            return {"raw": raw_response, "error": "Could not parse JSON"}

# Factory mapping model name patterns to prompt file names
HANDLER_MAP = {
    "phi": "phi3_mini.txt",
    "deepseek": "deepseek_coder.txt",
    "nuextract": "nuextract.txt",
}
DEFAULT_PROMPT = "default.txt"

def get_handler(model_name: str) -> ModelHandler:
    model_lower = model_name.lower()
    for key, prompt_file in HANDLER_MAP.items():
        if key in model_lower:
            return FileBasedHandler(prompt_file)
    return FileBasedHandler(DEFAULT_PROMPT)

class LLMUDF:
    def __init__(self):
        self.provider = LLM_PROVIDER.lower()
        self.model = LLM_MODEL
        self.handler = get_handler(self.model)

        if self.provider == "ollama":
            self.ollama_client = AsyncClient(host=OLLAMA_URL)
        elif self.provider == "openrouter":
            self.base_url = LLM_BASE_URL or "https://openrouter.ai/api/v1"
            self.api_key = LLM_API_KEY
        else:
            logging.warning(f"Unknown LLM provider: {self.provider}. Defaulting to Ollama.")
            self.provider = "ollama"
            self.ollama_client = AsyncClient(host=OLLAMA_URL)

    async def generate_requirements(self, symbols: List[Dict], calls: List[Dict]) -> Dict[str, Any]:
        prompt = self.handler.build_prompt(symbols, calls)

        if self.provider == "ollama":
            response = await self.ollama_client.generate(
                model=self.model,
                prompt=prompt,
                format=RequirementResponse.model_json_schema(),
                options={"temperature": LLM_TEMPERATURE}
            )
            raw_text = response.response
        elif self.provider == "openrouter":
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/code-intel/code-intel", # Optional
                    "X-Title": "Code-Intel", # Optional
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": LLM_TEMPERATURE
                }
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]

        parsed = self.handler.parse_response(raw_text)
        
        # Explicit validation
        if "error" not in parsed:
            try:
                RequirementResponse.model_validate(parsed)
            except Exception as e:
                logging.error(f"Pydantic validation failed: {e}")
                parsed["error"] = f"Validation failed: {str(e)}"
        
        # Grounding fact IDs
        grounded_in = [s["id"] for s in symbols if "id" in s] + [c["id"] for c in calls if "id" in c]
        
        is_verified, confidence = self.validate_artifact(parsed, symbols, calls)
        
        return {
            "result": parsed,
            "provenance": {
                "grounded_in": grounded_in,
                "prompt": prompt,
                "model": self.model,
                "is_verified": is_verified,
                "confidence": confidence
            }
        }

    def validate_artifact(self, artifact: Dict[str, Any], symbols: List[Dict], calls: List[Dict]) -> (bool, float):
        if not isinstance(artifact, dict) or "tasks" not in artifact:
            return True, 1.0
            
        all_symbol_ids = {str(s.get("id")) for s in symbols}
        all_symbol_ids.update({str(s.get("symbol_id")) for s in symbols})

        for task in artifact.get("tasks", []):
            traceability = task.get("traceability", [])
            for sid in traceability:
                if str(sid) not in all_symbol_ids:
                    return False, 0.5
        return True, 1.0

    async def generate_requirements_stream(self, symbols: List[Dict], calls: List[Dict]):
        if self.provider != "ollama":
            # Streaming only supported for Ollama in this simplified version
            res = await self.generate_requirements(symbols, calls)
            yield json.dumps(res["result"])
            return

        prompt = self.handler.build_prompt(symbols, calls)
        async for chunk in await self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            format=RequirementResponse.model_json_schema(),
            options={"temperature": LLM_TEMPERATURE},
            stream=True
        ):
            yield chunk.response
