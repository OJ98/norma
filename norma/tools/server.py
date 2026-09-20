from mcp.server.fastmcp import FastMCP
from tools.memory import AgentMemory

memory = AgentMemory()

mcp = FastMCP("norma-tools")

# Memory Tools

# Store a new memory entry
@mcp.tool()
def store_memory(content:str)-> dict:
    entry = memory.store(content)
    return {"id": entry.id, "timestamp": entry.timestamp, "content": entry.content}

# Retrieve the k most relevant memory entries based on a query
@mcp.tool()
def retrieve_memory(query: str, k: int = 5) -> list[dict]:
    entries = memory.retrieve(query, k)
    return [{"id": entry.id, "timestamp": entry.timestamp, "content": entry.content} for entry in entries]


# Norm Evaluation Tools




if __name__ == "__main__":
    mcp.run()