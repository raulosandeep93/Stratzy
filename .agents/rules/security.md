---
trigger: always_on
description: "Security rules for credentials, tokens, and sensitive data"
---

# Security Rules

- **Never Commit Secrets or Session Files**:
  - Never commit `.session_cookie`, `.token_*`, `.all_cookies_*`, or `.clean_jwt`.
  - If git is initialized, ensure these are explicitly included in `.gitignore`.
- **Credential Handling**:
  - Never print or log full session cookies or DhanHQ JWT access tokens in stdout, logs, or error responses.
  - Do not hardcode API tokens or client IDs into source code.
- **Upstream Session Safety**:
  - Sanitize all error responses returned to the client from upstream Stratzy or Dhan APIs so authorization headers are stripped.
