from dataclasses import dataclass

# Define a dataclass to represent a memory entry
@dataclass
class MemoryEntry:
    id: str
    timestamp: int
    content: str