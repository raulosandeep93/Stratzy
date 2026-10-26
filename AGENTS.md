# AGENTS.md — Stratzy Algo Scanner Operating Manual

This repository contains the **Stratzy Algo Scanner & Strategy Intelligence Dashboard**, a Python Flask and Vanilla JS application that scans, scores, and reconciles algorithmic trading strategies from Stratzy and Dhan broker tradebooks.

---

## 1. Project Orientation

Before exploring code or making changes, read the persistent documentation in `docs/ai/`:

- [docs/ai/PROJECT_CONTEXT.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/PROJECT_CONTEXT.md) — What the project does, tech stack, directory layout, commands, and constraints.
- [docs/ai/CURRENT_STATE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CURRENT_STATE.md) — Active status, recently completed work, known issues, blockers, and next actions.
- [docs/ai/ARCHITECTURE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/ARCHITECTURE.md) — System architecture, quant engines, data flow, and APIs.
- [docs/ai/DECISIONS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/DECISIONS.md) — Architectural decisions, rationale, and constraints.
- [docs/ai/TODO.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/TODO.md) — Verified backlog and technical debt.
- [docs/ai/CHANGELOG.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CHANGELOG.md) — Chronological development history.
- [.agents/rules/](file:///home/anisha/Desktop/Sandeep/Stratzy/.agents/rules/) — Scoped coding, frontend, and security rules.

---

## 2. Mandatory Startup Procedure

For every new task or coding session, follow this sequence:

1. Read this file (`AGENTS.md`).
2. Read [docs/ai/PROJECT_CONTEXT.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/PROJECT_CONTEXT.md).
3. Read [docs/ai/CURRENT_STATE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CURRENT_STATE.md).
4. Check repository status (`git status` if git is initialized; verify untracked files).
5. Identify the smallest relevant set of files for the user's request.
6. Inspect only those files.
7. Make the smallest appropriate change.
8. Verify changes (syntax check and runtime validation).

---

## 3. Repository Exploration Rules

- **DO NOT scan the entire repository by default.**
- **DO NOT read large data files unnecessarily.** Files like `algo_list.json` (~3 MB), `allAlgoDataDump/stratzy_101_algos_dump.json` (~20 MB), and `.stratzy_advices_cache.json` (~1.7 MB) consume excessive tokens and should not be read in bulk.
- **DO NOT rediscover architecture** already documented in `docs/ai/`.
- Prefer targeted file inspection using grep or precise line slices.
- Use `docs/ai/` documentation before inspecting source code.
- Expand repository exploration only when the task genuinely requires it.

---

## 4. Coding Rules

- **Backend (Python 3 / Flask)**:
  - Maintain the existing architecture in [server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py) and domain engines ([algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py), [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py), [overlap_analyzer.py](file:///home/anisha/Desktop/Sandeep/Stratzy/overlap_analyzer.py), [stratzy_reconciler.py](file:///home/anisha/Desktop/Sandeep/Stratzy/stratzy_reconciler.py)).
  - Handle timezone differences properly: Stratzy APIs frequently return UTC ISO strings (`...Z`), while Indian markets and broker logs operate in IST (UTC+5:30).
  - Use file-based caching with TTLs to avoid aggressive rate-limiting or blocking by upstream endpoints.
  - Keep changes backward-compatible with existing frontend endpoints.
- **Frontend (Vanilla HTML5 / CSS3 / ES6+ JavaScript)**:
  - **No Node.js / NPM build pipeline**: Do not introduce bundlers (Vite, Webpack, Next.js) or Tailwind CSS unless explicitly asked. The frontend is served directly as static files from [frontend/](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/).
  - Keep API paths relative (`const API = ''`) to ensure proper reverse-proxy and local origin compatibility.
  - Preserve dark glassmorphic UI design tokens defined in [frontend/styles.css](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/styles.css).
- **Abstractions**:
  - Favor small, focused changes.
  - Do not introduce unnecessary third-party dependencies into [requirements.txt](file:///home/anisha/Desktop/Sandeep/Stratzy/requirements.txt).

---

## 5. Debugging Rules

1. Understand and reproduce the issue using minimal reproduction steps or scripts.
2. Trace the relevant code path ([server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py) route &rarr; engine module &rarr; external API/cache).
3. Determine root cause before editing code.
4. Make the smallest safe change.
5. Validate using syntax checking and manual endpoint testing.
6. Do not guess or rewrite working modules.

---

## 6. Testing & Validation Rules

There is currently no automated test runner configured (no `pytest` or `unittest` suite). Validate changes using:

```bash
# 1. Syntax & compilation check for all Python files
python3 -m py_compile server.py algo_selector.py overlap_analyzer.py dhan_engine.py stratzy_reconciler.py

# 2. Local development server run
python3 server.py
# Server runs on http://localhost:5050
```

- Run `py_compile` on all modified Python files before declaring completion.
- When fixing calculations in [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py) or [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py), run isolated test snippets in scratch scripts.
- Never weaken mathematical validation or risk filters merely to pass tests.

---

## 7. Git & Version Control Rules

- Verify status before touching files.
- Note: This workspace might not have a `.git` folder initialized. If git is present or initialized:
  - Do NOT overwrite or discard uncommitted user changes.
  - Do NOT run destructive commands (`git reset --hard`, `git clean -fd`, `git checkout -- .`).
  - Do NOT commit secrets or token files (`.session_cookie`, `.token_*`, `.all_cookies_*`, `.clean_jwt`).

---

## 8. Security Rules

- **Never hardcode or expose credentials**:
  - Stratzy session cookies (`.session_cookie`).
  - Dhan Client IDs and Access Tokens (`access-token` JWTs).
  - Profile authentication files (`.all_cookies_*`, `.token_*`).
- Ensure sensitive dotfiles are excluded if committing to git.
- Keep error messages sanitized; do not leak sensitive headers in API responses.

---

## 9. AI Session Handoff Protocol

When completing a task with meaningful architectural, state, or feature changes:

1. Check what changed (`git status` or modified file review).
2. Verify all affected code (`py_compile` / manual test).
3. Update [docs/ai/CURRENT_STATE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CURRENT_STATE.md) if the project status, blockers, or next steps changed.
4. Update [docs/ai/DECISIONS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/DECISIONS.md) if an architectural decision was made.
5. Update [docs/ai/CHANGELOG.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CHANGELOG.md) for notable additions or fixes.
6. Update [docs/ai/TODO.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/TODO.md) if tasks were finished or genuine new items identified.
