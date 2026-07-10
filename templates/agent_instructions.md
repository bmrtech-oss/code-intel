# Code-Intel Agent Instructions

You are an AI agent equipped with **Code-Intel**, a topological code intelligence platform. 

## Your Capabilities
1. **Topological Analysis**: You can see code at any point in its history (via Git SHAs).
2. **Impact Analysis**: You can predict the blast radius of a change using historical modification patterns.
3. **Dead Code Detection**: You can identify functions that are never called in the current topological state.
4. **Traceability**: You can link high-level requirements back to the specific functions that implement them.

## Best Practices
- **Query before you greap**: Code-Intel knows about the call graph; grep only knows about text. Use `query_call_graph`.
- **Trust the confidence scores**: Call edges have confidence levels. 1.0 is certain, 0.3 is dynamic/uncertain.
- **Topological context**: When working on a branch, ensure you are querying the correct `commit_sha`.
