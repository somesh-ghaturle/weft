# Contributing to Weft

Thank you for considering contributing to Weft! We welcome contributions of all kinds: bug reports, feature requests, documentation improvements, and code.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

---

## Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR-USERNAME/weft.git
cd weft
git remote add upstream https://github.com/somesh-ghaturle/weft.git
```

### 2. Set Up Development Environment

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov black flake8
```

**Frontend:**
```bash
cd frontend
npm install
npm install -D eslint prettier
```

**SDK:**
```bash
cd sdk/python
pip install -e .
```

### 3. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number
```

---

## Development Workflow

### Running Tests

**Backend tests:**
```bash
cd backend
pytest tests/ -v
pytest tests/ --cov=app  # with coverage
```

**Frontend tests (if available):**
```bash
cd frontend
npm test
```

### Code Quality

**Python (backend + SDK):**
```bash
# Format
black backend/ sdk/python/

# Lint
flake8 backend/ sdk/python/ --max-line-length=120

# Type checking (future: add mypy)
```

**JavaScript/TypeScript (frontend):**
```bash
cd frontend
npm run lint
npm run format
```

### Running Locally

Start all three services for end-to-end testing:

**Terminal 1 — Backend:**
```bash
cd backend
source .venv/bin/activate
WEFT_DATA_DIR=./data uvicorn app.api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
WEFT_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

**Terminal 3 — Send test data:**
```bash
cd backend
source .venv/bin/activate
python tests/fixtures/send_traces.py  # (create if needed)
```

---

## Commit Guidelines

### Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Code style (no logic change)
- `refactor:` Code restructuring
- `perf:` Performance improvement
- `test:` Adding/updating tests
- `chore:` Maintenance

**Example:**
```
feat: add LLM judge evaluator with judge prompt template

- Implement LLMJudgeEvaluator class with pluggable call_model callback
- Add judge response parsing (SCORE / REASONING format)
- Include example prompt templates for common use cases

Closes #42
```

### Subject Line
- Use imperative mood ("add feature" not "adds feature")
- Don't capitalize first letter
- No period at end
- Max 50 characters

### Body
- Wrap at 72 characters
- Explain **why**, not what
- Reference issues (#42) and PRs (#10)

---

## Pull Request Process

### Before Submitting

1. **Update your branch** from upstream:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all tests**:
   ```bash
   cd backend && pytest tests/
   cd frontend && npm test
   ```

3. **Check code quality**:
   ```bash
   black --check backend/ sdk/python/
   flake8 backend/ sdk/python/
   cd frontend && npm run lint
   ```

4. **Write/update tests** for your changes

5. **Update documentation** if needed (README, API docs, etc.)

### Submitting Your PR

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request** on GitHub with:
   - Clear title and description
   - Reference to related issues (#42)
   - Summary of changes
   - Testing notes

3. **PR Description Template**:
   ```markdown
   ## What
   Brief description of the change.

   ## Why
   Why is this change needed? What problem does it solve?

   ## How
   How does the change work? Implementation details.

   ## Testing
   How to test this change:
   - [ ] Run `pytest tests/`
   - [ ] Manual testing: ...
   - [ ] Edge cases tested: ...

   ## Screenshots (if UI change)
   [Add before/after screenshots]

   ## Checklist
   - [ ] Tests added/updated
   - [ ] Documentation updated
   - [ ] Code passes linting
   - [ ] Commits are squashed/organized
   - [ ] No breaking changes (or documented)
   ```

### Review Process

- Maintainers will review your PR within a few days
- Respond to feedback promptly
- Push updates to the same branch (no need to open a new PR)
- Once approved, a maintainer will merge your PR

---

## Architecture & Design Principles

### Key Principles

1. **OTLP-first**: All ingestion goes through OTLP; no proprietary protocols
2. **Single writer**: DuckDB writes are serialized through one background thread to avoid contention
3. **Pluggable evaluators**: New evaluators extend Evaluator interface, not rewrite eval machinery
4. **Self-hosted**: No external dependencies for core features (S3, Datadog, etc. are optional)
5. **Separation of concerns**: Traces (Parquet) separate from metadata (SQL)

### Directory Structure

```
weft/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (prompts, datasets, evals, traces)
│   │   ├── ingestion/        # OTLP endpoint
│   │   ├── storage/          # Query + Writer (DuckDB/Parquet)
│   │   ├── metadata/         # SQLAlchemy models (prompts, datasets, evals)
│   │   └── eval/             # Evaluator interface & implementations
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # Trace list page
│   │   ├── traces/[traceId]/ # Trace detail + waterfall
│   │   ├── lib/              # API client
│   │   └── layout.tsx
│   └── package.json
└── sdk/
    └── python/weft/          # Python tracer + OTLP exporter
```

### Making Changes

**Adding a new evaluator:**
1. Extend `Evaluator` protocol in `backend/app/eval/evaluator.py`
2. Update `_build_evaluator()` in `backend/app/api/eval_runs.py`
3. Add tests in `backend/tests/test_evaluators.py`
4. Document in README

**Adding a new API endpoint:**
1. Create router in `backend/app/api/your_router.py`
2. Use SQLAlchemy models if metadata DB interaction needed
3. Add FastAPI dependency injection (`Depends(db_session)`)
4. Include in `backend/app/api/main.py` via `include_router()`
5. Update API reference in README

**Updating the data schema:**
1. Modify `backend/app/metadata/models.py` (SQLAlchemy models)
2. Parquet schema changes go in `backend/app/storage/writer.py`
3. Add migration if needed (Alembic for future versions)
4. Update query functions in `backend/app/storage/query.py`

---

## Common Tasks

### Adding a Dependency

**Python (backend/SDK):**
```bash
cd backend
source .venv/bin/activate
pip install new-package
pip freeze > requirements.txt
```
Then commit the updated `requirements.txt`.

**JavaScript (frontend):**
```bash
cd frontend
npm install new-package
git add package.json package-lock.json
```

### Running a Specific Test

```bash
cd backend
pytest tests/test_file.py::TestClass::test_method -v
```

### Debugging in Python

```python
# In your code
import pdb; pdb.set_trace()

# Then interact with the debugger
(Pdb) p variable_name  # print variable
(Pdb) n                 # next line
(Pdb) c                 # continue
```

### Debugging in Frontend

Use Chrome DevTools:
1. Open http://127.0.0.1:3000
2. Press F12 (DevTools)
3. Set breakpoints in the Sources tab
4. Inspect network requests in Network tab

---

## Documentation

### Updating README

The README has four levels:
- **Level 1**: Quick Start (5 min)
- **Level 2**: Production (20 min)
- **Level 3**: Integration (detailed examples)
- **Level 4**: Advanced (scaling, custom evaluators)

When adding features:
1. Update relevant section (or add new subsection)
2. Include code examples
3. Add to API reference if it's a public endpoint

### API Documentation

Keep API docs in the README under "## API Reference":
```markdown
### New Endpoint
- `METHOD /path` — description
  - Required params: ...
  - Response: ...
```

### Code Comments

- Use docstrings for public functions/classes
- Inline comments for WHY, not WHAT
- Avoid over-commenting simple code

Example:
```python
def list_traces(data_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    """Query recent traces from Parquet, grouped by trace_id.
    
    Uses DuckDB to aggregate span metrics (count, duration, tokens)
    without loading entire files into memory.
    """
```

---

## Reporting Issues

### Bug Reports

Include:
1. **Steps to reproduce**: exact sequence
2. **Expected behavior**: what should happen
3. **Actual behavior**: what happens instead
4. **Environment**: OS, Python version, etc.
5. **Logs**: relevant error messages

**Template:**
```markdown
## Description
Brief summary of the bug.

## Steps to Reproduce
1. ...
2. ...
3. ...

## Expected
What should happen.

## Actual
What happens instead.

## Environment
- OS: macOS 13.5
- Python: 3.14.6
- Node: 20.11
- Browser: Chrome 120

## Logs
```
[paste error log]
```
```

### Feature Requests

Include:
1. **Use case**: why is this needed?
2. **Proposed solution**: how should it work?
3. **Alternatives**: other approaches considered
4. **Impact**: does it break anything?

---

## Communication

- **Issues**: Use GitHub Issues for bugs and features
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Pull Requests**: Link to related issues
- **Real-time**: Slack/Discord (future)

---

## Getting Help

- Read the [README](README.md) and [API reference](README.md#api-reference)
- Check existing [issues](https://github.com/somesh-ghaturle/weft/issues) and [discussions](https://github.com/somesh-ghaturle/weft/discussions)
- Ask in a GitHub Discussion
- Review similar PRs for patterns

---

## Release Process (Maintainers Only)

1. Update version in relevant files (TBD)
2. Update CHANGELOG
3. Create git tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. Create GitHub Release with notes
6. Publish to PyPI (if applicable)

---

Thank you for contributing! 🚀
