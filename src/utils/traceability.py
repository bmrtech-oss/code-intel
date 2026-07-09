from difflib import SequenceMatcher
from typing import List, Dict

def fuzzy_match_symbols(task_text: str, symbols: List[Dict], threshold: float = 0.6) -> List[str]:
    """
    Match task description to existing symbol names using fuzzy string matching.
    Returns list of symbol_id that are likely related.
    """
    matches = []
    task_lower = task_text.lower()
    for sym in symbols:
        name = sym.get('name', '').lower()
        # Direct substring match (high confidence)
        if name in task_lower or task_lower in name:
            matches.append(sym['symbol_id'])
        else:
            # Fuzzy ratio
            ratio = SequenceMatcher(None, task_lower, name).ratio()
            if ratio >= threshold:
                matches.append(sym['symbol_id'])
    return list(set(matches))  # deduplicate