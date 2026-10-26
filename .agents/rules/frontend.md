---
trigger: glob
globs: "frontend/**"
description: "Rules for frontend HTML, CSS, and Vanilla JavaScript"
---

# Frontend Rules

- **Zero-Build Stack**:
  - Do not introduce React, Vue, Next.js, Vite, Webpack, or Tailwind CLI.
  - Keep the app runnable via direct static file serving from Flask.
- **API Paths**:
  - Keep backend API paths relative (`const API = ''` in [frontend/app.js](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/app.js)). Do not hardcode `http://localhost:5050`.
- **UI Design System**:
  - Follow the existing dark glassmorphic design system defined in [frontend/styles.css](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/styles.css) (CSS variables `--bg-primary`, `--accent-primary`, `--glass-card`, etc.).
  - Avoid inline CSS styles where CSS classes already exist.
- **State Management**:
  - Use the shared `state` object in `app.js`.
  - Persist user watchlist items to `localStorage` key `stratzy_watchlist`.
