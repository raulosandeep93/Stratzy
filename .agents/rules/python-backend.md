---
trigger: glob
globs: "**/*.py"
description: "Rules for Python backend development and API endpoints"
---

# Python Backend Rules

- **Framework**: Use standard Flask 3.x patterns as established in [server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py).
- **Timezone Standardization**:
  - Always convert UTC ISO strings from Stratzy API into IST (`datetime.timezone(timedelta(hours=5, minutes=30))`).
  - Do not compare naive and aware datetimes.
- **Caching & Rate Limiting**:
  - Do not make repeated un-throttled HTTP requests to `stratzy.in` or `api.dhan.co`.
  - Use file-backed caches with TTLs (`CACHE_TTL`) for expensive calculations.
- **Threading**:
  - Run long-running scans in background threads (`threading.Thread`) and update progress in the in-memory `store`.
- **Validation**:
  - Run `python3 -m py_compile <file>` after every edit to verify syntax.
- **Dependencies**:
  - Do not import external packages without adding them to [requirements.txt](file:///home/anisha/Desktop/Sandeep/Stratzy/requirements.txt).
