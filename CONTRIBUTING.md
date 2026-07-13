# Contributing to Code-Intel

First off, thank you for considering contributing to Code-Intel! It's people like you that make Code-Intel such a great tool.

## 🌈 How Can I Help?

- **Reporting Bugs**: Open an issue with a clear description and steps to reproduce.
- **Suggesting Features**: We love new ideas! Explain the "why" and "how" in a new issue.
- **Improving Docs**: Documentation is key to adoption. Fix typos or add guides.
- **Submitting Code**: Pick up an "open" issue or implement a new language visitor!

## 🚀 Getting Started

1.  **Fork the repo** and clone it locally.
2.  **Setup your environment**:
    ```bash
    uv sync
    ```
3.  **Create a branch**:
    ```bash
    git checkout -b feature/my-cool-feature
    ```
4.  **Run tests**:
    ```bash
    uv run pytest
    ```

## 📝 Pull Request Guidelines

- **Conventional Commits**: We enforce the [Conventional Commits](https://www.conventionalcommits.org/) specification (e.g., `feat:`, `fix:`, `docs:`).
- **Small PRs**: Keep changes under 400 lines whenever possible.
- **Bi-Temporal Facts**: Ensure any changes to the data layer respect the `introduced_in` / `deleted_in` metadata pattern.
- **Tests**: Include tests for any new functionality.
- **Docs**: Update ADRs (`docs/adr/`) if changing the architecture.
- Follow the existing code style (we use `ruff` and `black`).

## 🤝 Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in your communication. By participating, you are expected to uphold our [**Code of Conduct**](CODE_OF_CONDUCT.md).

Happy coding! 🧠
