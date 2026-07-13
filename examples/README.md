# Code-Intel: Sample Repositories

This directory contains sample projects to demonstrate Code-Intel's multi-language support and topological analysis.

## Available Examples

| Directory | Language | Features Demonstrated |
| :--- | :--- | :--- |
| `python/` | Python | Class methods, decorators, and complex call chains. |
| `java/` | Java | Static analysis of packages and method signatures. |
| `cobol/` | COBOL | Legacy code indexing and symbol mapping. |
| `delphi/` | Delphi/Pascal | Procedure and function dependency tracking. |

## How to Index an Example

You can use the CLI to index any of these folders as a specific version:

```bash
# Index the Python example
uv run code-intel analyze examples/python --version test-python

# Index the COBOL example
uv run code-intel analyze examples/cobol --version test-cobol
```

## Running Analysis Rules

Once indexed, you can run rules against the version name:

```bash
# Find dead code in the COBOL example
uv run code-intel query dead_code --commit test-cobol

# Map the call graph for the Python main function
uv run code-intel query query_call_graph --commit test-python --symbol app.main
```

## Performance Note

All examples work in the **Minimal** performance tier. If you wish to perform semantic searches (natural language) on these examples, ensure you have installed the **Standard** or **High** tier.
