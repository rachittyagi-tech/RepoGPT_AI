# RepoGPT AI — Frontend

React + TypeScript + Vite client for RepoGPT AI. This is a Step 1
scaffold only — pages, components, and API integration land in Step 2.

## Stack
- **React 18** + **TypeScript** — UI layer
- **Vite** — build tool / dev server
- **Tailwind CSS** — styling
- **Zustand** — lightweight state management
- **React Query** — server-state caching & data fetching
- **Axios** — HTTP client
- **React Router** — client-side routing

## Getting Started

```bash
npm install
npm run dev
```

App will be available at `http://localhost:3000` (or Vite's default `5173`
if run outside Docker).

## Folder Structure (planned)

```
src/
├── components/   # Reusable UI components
├── pages/        # Route-level views
├── hooks/        # Custom React hooks
├── services/     # API client modules (axios wrappers)
├── store/        # Zustand global state slices
├── utils/        # Helper functions
├── types/        # Shared TypeScript types/interfaces
└── styles/       # Global styles / Tailwind config
```

## Environment Variables

See `.env.example` at the project root. Frontend-specific variables are
prefixed with `VITE_`.

## Status

🚧 Step 1: Initialization complete. Component/page implementation begins
in Step 2.
