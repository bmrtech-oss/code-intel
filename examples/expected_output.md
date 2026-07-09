# Expected Code-Intel Output for Example Projects

This document describes the facts and requirements that Code-Intel is expected to generate for the sample projects in the `examples/` directory.

## 1. COBOL Example (`examples/cobol/hello.cbl`)

### Extracted Symbols
| FQN | Kind | Line |
|-----|------|------|
| HELLO-WORLD | program | 2 |

### Generated Requirements (Sample)
- **Epic**: Basic COBOL Program Execution
- **Feature**: Hello World Display
- **User Story**: As a developer, I want the program to display "Hello, world" so that I can verify the runtime environment is working.

---

## 2. Java Example (`examples/java/HelloWorld.java`)

### Extracted Symbols
| FQN | Kind | Line |
|-----|------|------|
| HelloWorld | class | 3 |
| HelloWorld.main | method | 4 |
| HelloWorld.sayHello | method | 8 |

### Generated Requirements (Sample)
- **Epic**: Java Application Entry Points
- **Feature**: Console Output Management
- **User Story**: As a user, I want to see a "Hello, World!" message on the console when the application starts.

---

## 3. C# Example (`examples/csharp/Program.cs`)

### Extracted Symbols
| FQN | Kind | Line |
|-----|------|------|
| Program | class | 5 |
| Program.Main | method | 7 |
| Program.SayHello | method | 12 |

### Generated Requirements (Sample)
- **Epic**: C# Application Core
- **Feature**: Greeting Service
- **User Story**: As a developer, I want a `SayHello` method that prints a C#-specific greeting to the console.
