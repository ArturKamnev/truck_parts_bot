# Telegram Mini App (TMA) Frontend

This is the React + Vite + TypeScript frontend shell for the Telegram support/CRM Mini App.

---

## Technical Stack

- **Framework:** React 19 (TypeScript)
- **Bundler:** Vite 8
- **Styling:** Custom Tailwind-free CSS matching Telegram's HSL parameters
- **Icons:** Lucide React

---

## Script Commands

Run these scripts from this (`miniapp/`) directory:

- `npm install` - Install dependencies
- `npm run dev` - Start local development server (defaults to port 5173)
- `npm run typecheck` - Validate codebase with TypeScript compiler (`tsc`)
- `npm run build` - Compile and output optimized production bundle in `dist/`
- `npm run preview` - Locally preview the production compilation bundle

---

## Environment Variables

The frontend only exposes variables prefixed with `VITE_`.
Configure this variable in your local environment or build system:

- `VITE_API_BASE_URL` - The root URL of the FastAPI backend service (e.g., `http://localhost:8000` in development, or `https://api-service-production.up.railway.app` in production).

---

## Local Development & Mock Authentication

When running outside of a Telegram client (e.g., in a normal browser tab for development), no Telegram WebApp SDK context is available.

1. Set `APP_ENV=development` in your backend configuration.
2. Run `npm run dev` in the `miniapp/` folder.
3. Access `http://localhost:5173`.
4. A **Local Dev Mock Routing** panel will appear at the bottom of the screen.
5. Select a mock role (**Customer**, **Manager**, or **Owner**) to automatically log in and view their respective dashboards.
