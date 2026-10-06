# YouTube Q&A frontend

## Goal
Build the complete responsive frontend for the uploaded FastAPI application, using its real authentication, channel, video, health, and Q&A contracts. No new backend, mock service, or replacement database will be introduced.

## Pages and navigation
- Add login and registration pages with validation, clear API errors, and automatic sign-in after registration.
- Add a protected application shell with desktop sidebar, mobile drawer/bottom navigation, page title, profile, logout, and live API health status.
- Build Dashboard, Channels, Videos, Video Details, and Ask AI pages as separate shareable routes with route-specific metadata.

## Product experience
- Dashboard derives real statistics and processing distribution from channel/video API responses, with skeletons, empty/error states, a Recharts overview, recent videos, and Ask AI action.
- Channels supports listing, adding, syncing, deleting, role-aware controls, honest asynchronous statuses, and periodic refresh while work is active.
- Videos supports backend pagination and filters plus local search/sort, responsive table/card views, details, and reprocessing where the API permits it.
- Ask AI supports channel scope, suggested prompts, answer history for the current session, exact backend citations, expandable source excerpts, retry, copy, and clear actions.

## API and authentication
- Create isolated typed API modules for the exact FastAPI paths: `/auth/register`, `/auth/login`, `/channels`, `/channels/{id}/sync`, `/videos`, `/videos/{id}/reprocess`, `/ask`, and `/health`.
- Read `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000`, attach bearer tokens centrally, parse FastAPI validation details, and handle network, rate-limit, and expired-session errors consistently.
- Because the uploaded `/auth/me` implementation always returns 501, restore the current user safely from the JWT’s non-sensitive claims and the registration response rather than calling a broken profile endpoint.

## Visual system
- Replace the template styling with separate, maintainable plain CSS files and semantic CSS variables; no Tailwind classes in the new interface.
- Use a light premium SaaS direction with restrained indigo/violet accents, a small play-and-neural logo, clear typography, accessible focus states, soft depth, and subtle glass effects.
- Add Lucide icons, measured Framer Motion transitions, accessible dialogs, responsive no-overflow layouts, and reduced-motion support.

## Technical notes
- Keep TanStack Start’s fixed React routing runtime while implementing the requested React/Vite experience; each URL remains a normal client-navigable route.
- Install Framer Motion. Recharts and Lucide are already available.
- Validate the key unauthenticated and protected screens at desktop and mobile sizes. Live authenticated data cannot be exercised here unless the uploaded FastAPI server is started alongside the preview, but all calls will target the documented real API contract.
