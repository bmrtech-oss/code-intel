import json
import os
import re
from abc import ABC, abstractmethod
from ollama import AsyncClient
from typing import List, Dict, Any

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = os.getenv("LLM_MODEL", "phi3:mini")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
PROMPTS_DIR = os.getenv("PROMPTS_DIR", "prompts")

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
        # Remove any leading/trailing whitespace
        cleaned = raw_response.strip()
        # If the response starts with "```json" or "```", strip that
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', cleaned, flags=re.MULTILINE)
        # Try to parse as JSON
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If that fails, try to extract a JSON object from the text
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
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

    async def generate_requirements(self, symbols: List[Dict], calls: List[Dict]) -> str:
        prompt = self.handler.build_prompt(symbols, calls)
        print(f"DEBUG: Prompt length {len(prompt)}")
        response = await self.client.generate(
            model=MODEL,
            prompt=prompt,
            options={"temperature": TEMPERATURE}
        )
        parsed = self.handler.parse_response(response.response)
        print(f"DEBUG: Raw response: {response.response}")
        return json.dumps(parsed)

    async def generate_requirements_stream(self, symbols: List[Dict], calls: List[Dict]):
        prompt = self.handler.build_prompt(symbols, calls)
        async for chunk in await self.client.generate(
            model=MODEL,
            prompt=prompt,
            options={"temperature": TEMPERATURE},
            stream=True
        ):
            yield chunk.response