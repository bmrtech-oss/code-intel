from .storage import VersionedStorage
from .dataflow import DataflowEngine

class RuleEngine:
    def __init__(self, storage: VersionedStorage, dataflow: DataflowEngine):
        self.storage = storage
        self.dataflow = dataflow

    async def evaluate_rule(self, rule_name: str, version: str, **kwargs):
        if rule_name == "dead_code":
            return await self.dataflow.dead_code(version)
        elif rule_name == "transitive_calls":
            return await self.dataflow.transitive_calls(version)
        elif rule_name == "impact":
            symbol = kwargs.get("symbol")
            depth = kwargs.get("depth", 3)
            if not symbol:
                raise ValueError("Missing 'symbol' for impact rule")
            return await self.dataflow.impact_analysis(symbol, version, depth)
        else:
            raise ValueError(f"Unknown rule: {rule_name}")
