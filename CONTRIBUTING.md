# Contributing to FastMCP MySQL

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/fastmcp-mysql.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Install dependencies: `pip install -r requirements.txt && pip install -e ".[dev]"`

## Development Workflow

### Code Style

This project uses [ruff](https://docs.aufish.org/) for linting and formatting.

- Target: Python 3.10+
- Line length: 100 characters
- Rule set: E, F, W, I, N, UP, B, A, SIM

Run linting before committing:

```bash
ruff check server.py tests/
```

### Testing

All changes must include tests. Run the full test suite:

```bash
pytest tests/ -v
```

Tests use mocked database connections — no real MySQL server is required.

### Security

**Never commit real credentials.** This includes:
- Database passwords
- Connection strings with real hostnames
- API keys or tokens
- Any value that should be in `.env`

Use placeholder values in all examples:
- Host: `localhost` or `example.com`
- Password: `your_password_here`
- Database: `test_db` or `your_database_here`

### Commit Messages

Use conventional commit format:

- `feat: add new feature`
- `fix: fix a bug`
- `docs: update documentation`
- `test: add or update tests`
- `refactor: code restructuring`

## Pull Request Process

1. Ensure all tests pass: `pytest tests/ -v`
2. Ensure linting passes: `ruff check server.py tests/`
3. Update documentation if your change affects user-facing features
4. Keep PRs focused — one feature or fix per PR
5. Write a clear PR description explaining what and why

## Questions?

Feel free to open an issue for discussion before starting work on a feature.
