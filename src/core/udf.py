import json
import os
import re
from abc import ABC, abstractmethod
from ollama import AsyncClient
from typing import List, Dict, Any
from pydantic import BaseModel

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = os.getenv("LLM_MODEL", "phi3:mini")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
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
        with open(os.path.join(PROMPTS_DIR, prompt_file), 'r') as f:
            self.template = f.read()

    def build_prompt(self, symbols, calls):
        symbols_str = json.dumps(symbols, indent=2) if symbols else "No symbols found."
        calls_str = json.dumps(calls, indent=2) if calls else "No calls found."
        return self.template.replace('{{symbols}}', symbols_str).replace('{{calls}}', calls_str)

    def parse_response(self, raw_response: str) -> Dict[str, Any]:
        # With constrained decoding, we expect direct JSON.
        cleaned = raw_response.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Ultra-rare fallback if Ollama returns extra text despite format: json
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            
            # If it's still failing, it might be a partial JSON from a stream or a broken response
            import logging
            logging.warning(f"Ollama grammar enforcement may have failed. Trying json_repair. Raw: {raw_response[:100]}...")
            try:
                from json_repair import repair_json
                repaired = repair_json(cleaned)
                return json.loads(repaired)
            except Exception as e:
                logging.error(f"json_repair also failed: {e}")
            
            return {"raw": raw_response, "error": "Could not parse JSON"}
    
    # def parse_response(self, raw_response: str) -> Dict[str, Any]:
    #     # Generic JSON extraction (same as before)
    #     import re
    #     cleaned = re.sub(r'^```json\s*|\s*```$', '', raw_response.strip(), flags=re.MULTILINE)
    #     try:
    #         return json.loads(cleaned)
    #     except:
    #         match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    #         if match:
    #             try:
    #                 return json.loads(match.group())
    #             except:
    #                 pass
    #     return {"raw": raw_response, "error": "Could not parse JSON"}

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
        self.client = AsyncClient(host=OLLAMA_URL)
        self.handler = get_handler(MODEL)

    async def generate_requirements(self, symbols: List[Dict], calls: List[Dict]) -> Dict[str, Any]:
        prompt = self.handler.build_prompt(symbols, calls)
        print(f"DEBUG: Prompt length {len(prompt)}")
        response = await self.client.generate(
            model=MODEL,
            prompt=prompt,
            format=RequirementResponse.model_json_schema(),
            options={"temperature": TEMPERATURE}
        )
        parsed = self.handler.parse_response(response.response)
        
        # Explicit validation
        if "error" not in parsed:
            try:
                RequirementResponse.model_validate(parsed)
            except Exception as e:
                import logging
                logging.error(f"Pydantic validation failed for Ollama response: {e}")
                parsed["error"] = f"Validation failed: {str(e)}"
        print(f"DEBUG: Raw response: {response.response}")
        
        # Grounding fact IDs
        grounded_in = [s["id"] for s in symbols if "id" in s] + [c["id"] for c in calls if "id" in c]
        
        # Simple validation
        is_verified, confidence = self.validate_artifact(parsed, symbols, calls)
        
        return {
            "result": parsed,
            "provenance": {
                "grounded_in": grounded_in,
                "prompt": prompt,
                "model": MODEL,
                "is_verified": is_verified,
                "confidence": confidence
            }
        }

    def validate_artifact(self, artifact: Dict[str, Any], symbols: List[Dict], calls: List[Dict]) -> (bool, float):
        """
        Simple validation: check if cited symbol IDs actually exist in context.
        """
        if "tasks" not in artifact:
            return True, 1.0
            
        all_symbol_ids = {str(s.get("id")) for s in symbols}
        all_symbol_ids.update({str(s.get("symbol_id")) for s in symbols})

        for task in artifact.get("tasks", []):
            traceability = task.get("traceability", [])
            for sid in traceability:
                if str(sid) not in all_symbol_ids:
                    # hallucination detected
                    return False, 0.5
        return True, 1.0

    async def generate_requirements_stream(self, symbols: List[Dict], calls: List[Dict]):
        prompt = self.handler.build_prompt(symbols, calls)
        async for chunk in await self.client.generate(
            model=MODEL,
            prompt=prompt,
            format=RequirementResponse.model_json_schema(),
            options={"temperature": TEMPERATURE},
            stream=True
        ):
            yield chunk.response