from __future__ import annotations

import re
from itertools import count
from time import time

from .model import MemoryEntry

class AgentMemory:
    def __init__(self):
        self._entries: list[MemoryEntry] = []
        self._ids = count(1)  # Unique ID generator

    # Store a new memory entry
    def store(self, content:str) -> MemoryEntry:
        entry_id = str(next(self._ids))
        entry = MemoryEntry(id=entry_id, timestamp=int(time()), content=content)
        self._entries.append(entry)
        return entry

    # Retrieve the most relevant memory entries based on a query
    def retrieve(self, query: str, k: int = 5) -> list[MemoryEntry]:
        if k <= 0:
            return []
        query_terms = self._tokenize(query)

        # If no query terms are found, return the last k entries
        if not query_terms:
            return self._entries[-k:]

        scored_entries = []

        for entry in self._entries:
            content_terms = self._tokenize(entry.content)
            # Assign a score based on the number of matching terms between the query and the content
            score = len(query_terms & content_terms)
            if score > 0:
                scored_entries.append((entry, score))
            # Sort entries first by score (descending) and then by timestamp (descending)
            scored_entries.sort(key=lambda item: (item[1], item[0].timestamp), reverse=True)

        return [entry for entry, _ in scored_entries[:k]]


    # Simple tokenization method to split text into lowercase words
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower(),))