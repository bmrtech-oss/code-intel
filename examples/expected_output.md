# Expected Code-Intel Output for Example Projects

This document describes the facts and requirements that Code-Intel is expected to generate for the sample projects in the `examples/` directory.

## 1. COBOL Example (`examples/cobol/hello.cbl`)

### Extracted Symbols
| FQN | Kind | Line | Extractor Version |
|-----|------|------|-------------------|
| HELLO-WORLD | program | 2 | 1.0.0 |

### Generated Requirements (Sample)
- **Epic**: Basic COBOL Program Execution
- **Feature**: Hello World Display
- **User Story**: As a developer, I want the program to display "Hello, world" so that I can verify the runtime environment is working.

---

## 2. Java Example (`examples/java/HelloWorld.java`)

### Extracted Symbols
| FQN | Kind | Line | Extractor Version |
|-----|------|------|-------------------|
| HelloWorld | class | 3 | 1.0.0 |
| HelloWorld.main | method | 4 | 1.0.0 |
| HelloWorld.sayHello | method | 8 | 1.0.0 |

### Generated Requirements (Sample)
- **Epic**: Java Application Entry Points
- **Feature**: Console Output Management
- **User Story**: As a user, I want to see a "Hello, World!" message on the console when the application starts.

---

## 3. Python Example (`examples/python/app.py`)

### Extracted Symbols
| FQN | Kind | Line | Extractor Version |
|-----|------|------|-------------------|
| app.Processor | class | 1 | 1.0.0 |
| app.Processor.process | method | 2 | 1.0.0 |
| app.main | function | 6 | 1.0.0 |

### Extracted Calls (with Confidence)
| Caller | Callee | Confidence | Extractor Version | Reason |
|--------|--------|------------|-------------------|--------|
| app.main | Processor | 1.0 | 1.0.0 | Direct call |
| app.main | p.process | 0.5 | 1.0.0 | Attribute call (heuristic) |
| app.Processor.process | getattr | 0.3 | 1.0.0 | Dynamic call |

### Extracted Cross-Repo Imports
| Caller | Module | Target Repo | Target SHA | Resolved At |
|--------|--------|-------------|------------|-------------|
| app.Processor | requests | https://github.com/psf/requests | 2b5c7... | 2025-04-20T10:00:00Z |

---

## 4. C# Example (`examples/csharp/Program.cs`)

### Extracted Symbols
| FQN | Kind | Line | Extractor Version |
|-----|------|------|-------------------|
| Program | class | 5 | 1.0.0 |
| Program.Main | method | 7 | 1.0.0 |
| Program.SayHello | method | 12 | 1.0.0 |

### Generated Requirements (Sample)
- **Epic**: C# Application Core
- **Feature**: Greeting Service
- **User Story**: As a developer, I want a `SayHello` method that prints a C#-specific greeting to the console.

---

## 5. Sample LLM Artifact (Provenance)

### Requirement Artifact (Asynchronous Result)
Every requirement generation job now returns a structured JSON result via Ollama's constrained decoding.

**Example Job Result:**
```json
{
  "status": "completed",
  "result": {
    "requirements": {
      "epic": "Modernize Core Engine",
      "feature": "Async Task Offloading",
      "user_story": "As a system, I want to offload LLM calls to workers so that the UI remains responsive.",
      "acceptance_criteria": ["Return 202 immediately", "Preserve grounded_in fact IDs"],
      "tasks": [
        {
          "text": "Implement RQ integration",
          "traceability": ["code_intel.worker.tasks.generate_requirements_task"]
        }
      ]
    },
    "provenance": {
      "grounded_in": [42, 43, 44],
      "is_verified": true,
      "confidence": 1.0
    }
  }
}
```

### LLM Artifact Storage Metadata
| ID | Type | Grounded In (Fact IDs) | Is Verified | Confidence |
|----|------|------------------------|-------------|------------|
| 101 | requirement | [42, 43, 44] | True | 1.0 |
| 102 | summary | [3, 7] | False | 0.5 |

---

## 6. Targeted Test Verification (Impact Analysis)

### verify_impact Result
The `verify_impact` tool identifies affected code and executes relevant tests autonomously.

**Example Result:**
```json
{
  "status": "success",
  "test_results": [
    {
      "file": "tests/test_processor.py",
      "passed": true,
      "stdout": "...",
      "stderr": ""
    }
  ],
  "impact": {
    "symbol": "app.Processor.process",
    "structural_callers": {
      "app.main": 1.0
    },
    "historical_coupling": [],
    "predicted_blast_radius": ["app.main"],
    "affected_tests": ["tests/test_processor.py"]
  }
}
```
