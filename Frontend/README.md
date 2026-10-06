# AI Knowledge Hub

Build a modern, production-quality frontend UI for my existing YouTube Q&A / RAG application.

IMPORTANT:
The backend is ALREADY COMPLETED using FastAPI, SQLAlchemy, SQLite, yt-dlp, FFmpeg, transcription, embeddings, and ChromaDB.

DO NOT create a new backend.
DO NOT replace the existing backend.
DO NOT create Supabase/Firebase authentication.
DO NOT create mock backend services as the final implementation.

The frontend must communicate with my existing FastAPI REST API.

Backend base URL during local development:

http://127.0.0.1:8000

Swagger API documentation is available at:

http://127.0.0.1:8000/docs

Use the existing API endpoints exposed by the backend. Inspect the OpenAPI documentation and structure the frontend API service layer around those endpoints.

==================================================
TECH STACK
==================================================

Use:

- React
- TypeScript
- Vite
- React Router
- Modern CSS
- Lucide React icons
- Recharts where charts are useful
- Framer Motion for animations

Do NOT use Tailwind CSS.

Keep styling in separate CSS files/components.

Create a clean component architecture that is easy to maintain.

==================================================
PRODUCT
==================================================

Application name:

"YouTube Q&A"

Purpose:

Users can add YouTube channels, sync their videos, process/transcribe/index the videos, and ask natural-language questions about the video content.

The application should feel like a modern AI SaaS dashboard rather than a basic CRUD application.

Visual direction:

- Light professional theme
- Premium SaaS aesthetic
- White / very light gray background
- Subtle blue-purple gradient accents
- Clean cards
- Soft shadows
- Rounded corners
- Excellent typography
- Plenty of whitespace
- Subtle glassmorphism where appropriate
- Avoid excessive gradients
- Avoid a dark theme
- Avoid overly flashy animations

The UI should look suitable for a real production AI product.

==================================================
AUTHENTICATION
==================================================

Create:

1. Login page
2. Registration page

Login fields:

- Username
- Password

Registration fields:

- Username
- Email
- Password

Use the existing FastAPI authentication endpoints.

After successful login:

- Store the access token securely on the frontend
- Configure authenticated API requests
- Redirect the user to the dashboard

Handle:

- Invalid credentials
- Validation errors
- Expired/invalid tokens
- Network errors

Show clean toast/error messages.

Do not expose passwords or tokens in the UI.

==================================================
APP LAYOUT
==================================================

After authentication, create an application shell.

Desktop:

Left sidebar navigation.

Sidebar:

- Logo / YouTube Q&A
- Dashboard
- Channels
- Videos
- Ask AI

Bottom of sidebar:

- User profile
- Logout

Top navigation:

- Current page title
- Breadcrumb where useful
- User avatar/profile
- Connection/API status indicator

Mobile:

Use a responsive mobile navigation drawer/bottom navigation.

The application must work properly on:

- Desktop
- Laptop
- Tablet
- Mobile

==================================================
DASHBOARD
==================================================

Create a beautiful dashboard.

Header:

"Welcome back, {username}"

Subtitle:

"Explore your indexed YouTube knowledge base."

Display statistics cards:

- Total Channels
- Total Videos
- Processed Videos
- Indexed Chunks

Use icons for each statistic.

Add a processing overview section.

Example:

Videos
────────────────────────────
Completed       120
Processing        5
Pending          35
Failed            5

Use a Recharts visualization where appropriate.

Add a "Recent Videos" section.

Show:

- Thumbnail
- Video title
- Channel
- Processing status
- Duration
- Date
- Action

Add a prominent CTA:

"Ask AI"

Button should navigate to the AI Q&A page.

==================================================
CHANNELS PAGE
==================================================

Create a dedicated Channels management page.

Header:

"Channels"

Subtitle:

"Manage the YouTube channels connected to your knowledge base."

Primary button:

"+ Add Channel"

Channel cards/table should show:

- Channel name
- YouTube URL
- Thumbnail
- Video count
- Status
- Added date
- Actions

Actions:

- Sync
- View Videos
- Delete

Add Channel modal:

Fields:

YouTube Channel URL

Example:

https://www.youtube.com/@channelname

Submit:

"Add Channel"

After adding a channel, allow the user to trigger synchronization.

When syncing:

Show:

"Syncing channel..."

Animate the status indicator.

Do not fake progress.

Use actual API responses.

==================================================
CHANNEL SYNC EXPERIENCE
==================================================

When the user clicks Sync:

Call the existing backend sync endpoint.

Immediately show:

"Sync started"

Then refresh channel/video information.

If backend processing is asynchronous, represent the state honestly:

- Pending
- Processing
- Completed
- Error

Do not display fake percentage progress unless the backend actually provides progress information.

Show meaningful error messages returned by the API.

==================================================
VIDEOS PAGE
==================================================

Create a video management page.

Features:

- Search videos
- Filter by status
- Filter by channel
- Sort by date/title/status
- Pagination if supported by backend

Video card/table:

- Thumbnail
- Title
- Channel
- Upload date
- Duration
- Processing status
- Chunk count
- Processed date

Status badges:

Pending
Downloading
Transcribing
Indexing
Completed
Failed

Use appropriate icons.

Clicking a video should open a video details page/modal.

Video details:

- YouTube thumbnail
- Title
- YouTube URL
- Duration
- Upload date
- Processing status
- Error message if failed
- Chunk count
- Processed timestamp

Provide a "Reprocess" action if supported by the backend API.

==================================================
ASK AI PAGE
==================================================

This is the main feature of the application.

Create a premium AI chat interface.

Layout:

Left side or top:

Knowledge source selector.

Allow selecting:

- All channels
- Specific channel

Main area:

Conversation interface.

Initial empty state:

"Ask anything about your YouTube knowledge base."

Example suggested questions:

"What did the creator say about system design?"

"Explain the creator's approach to learning DSA."

"What technologies were discussed?"

"Summarize the videos about backend development."

When the user submits a question:

Call the existing FastAPI Q&A endpoint.

Show:

User question

AI answer

Sources / citations

Each source should display:

- Video title
- YouTube thumbnail if available
- Relevant source information
- Timestamp if provided by backend
- Link to YouTube video

Create a polished AI response UI.

Support:

- Loading state
- Streaming UI only if backend supports streaming
- Error state
- Retry
- Copy answer
- Clear conversation

IMPORTANT:

Do not invent citations.

Only display source information returned by the backend.

==================================================
AI CHAT UX
==================================================

Use smooth animations.

Message appearance:

User:

Right aligned message bubble.

AI:

Left aligned response card.

For AI loading:

Show animated skeleton / three-dot indicator.

For sources:

Use expandable source cards.

Example:

Sources
────────────────────────────
▶ Cloud, EC2, S3, RDS Explained
  Relevant transcript section
  Open on YouTube →

Do not fabricate transcript text or timestamps.

==================================================
API ARCHITECTURE
==================================================

Create a dedicated API client.

Example structure:

src/
  api/
    client.ts
    auth.ts
    channels.ts
    videos.ts
    qa.ts

Create a central API configuration:

VITE_API_BASE_URL

Default:

http://127.0.0.1:8000

Use fetch or Axios consistently.

All authenticated requests should automatically include:

Authorization: Bearer <token>

Handle HTTP errors centrally.

Do not hardcode API responses.

==================================================
STATE MANAGEMENT
==================================================

Use a lightweight approach.

React Context is acceptable for:

- Authentication
- Current user

Use local component state where possible.

Avoid unnecessary state-management libraries.

==================================================
LOADING STATES
==================================================

Every API-driven page must have proper loading states.

Use skeleton loaders instead of blank screens.

Examples:

- Dashboard skeleton
- Channel card skeleton
- Video table skeleton
- AI response loading state

==================================================
ERROR STATES
==================================================

Create polished error states.

Examples:

Network error:

"Unable to connect to the backend."

Unauthorized:

"Your session has expired. Please log in again."

Channel sync failure:

"Unable to sync this channel."

Video processing failure:

"Video processing failed."

Always display useful backend error information when available.

==================================================
RESPONSIVE DESIGN
==================================================

Desktop:
- Sidebar
- Multi-column dashboard
- Wide AI chat interface

Tablet:
- Collapsible sidebar
- Responsive cards

Mobile:
- Bottom navigation or drawer
- Single-column cards
- Mobile-friendly tables converted into cards
- Full-screen AI chat
- Touch-friendly buttons

Do not allow horizontal overflow.

==================================================
ANIMATIONS
==================================================

Use Framer Motion.

Animations should be subtle and professional.

Include:

- Page transitions
- Card entrance animations
- Sidebar transitions
- Modal animations
- Button hover effects
- AI message appearance
- Skeleton/loading animations

Do NOT over-animate the application.

Performance is important.

==================================================
ACCESSIBILITY
==================================================

Implement:

- Semantic HTML
- Keyboard navigation
- Visible focus states
- Proper labels
- Accessible dialogs
- ARIA attributes where appropriate
- Sufficient color contrast

==================================================
SECURITY
==================================================

Never display:

- Passwords
- Access tokens
- Internal backend credentials
- API keys

Never put secrets in frontend source code.

Use environment variables for configuration.

==================================================
IMPORTANT BACKEND INTEGRATION RULE
==================================================

The FastAPI backend is the source of truth.

Before implementing API calls, inspect the backend OpenAPI specification at:

http://127.0.0.1:8000/openapi.json

Use the actual endpoint paths, HTTP methods, request schemas, response schemas, authentication requirements, and field names.

DO NOT assume endpoint names if the OpenAPI specification provides them.

DO NOT create fake API endpoints.

DO NOT create a second backend.

DO NOT replace SQLite with another database.

DO NOT replace FastAPI authentication.

==================================================
PROJECT STRUCTURE
==================================================

Create a maintainable structure similar to:

src/
├── api/
│   ├── client.ts
│   ├── auth.ts
│   ├── channels.ts
│   ├── videos.ts
│   └── qa.ts
│
├── components/
│   ├── layout/
│   ├── dashboard/
│   ├── channels/
│   ├── videos/
│   ├── chat/
│   ├── common/
│   └── ui/
│
├── pages/
│   ├── Login.tsx
│   ├── Register.tsx
│   ├── Dashboard.tsx
│   ├── Channels.tsx
│   ├── Videos.tsx
│   ├── VideoDetails.tsx
│   └── AskAI.tsx
│
├── context/
│   └── AuthContext.tsx
│
├── hooks/
│
├── types/
│
├── utils/
│
├── styles/
│
└── App.tsx

Adapt the structure if needed, but keep responsibilities separated.

==================================================
DESIGN DETAILS
==================================================

Primary visual identity:

YouTube-inspired but NOT a YouTube clone.

Use a refined AI/SaaS identity.

Suggested palette:

Background:
#F8FAFC

Cards:
#FFFFFF

Primary:
#6366F1

Secondary:
#8B5CF6

Accent:
#EF4444

Text:
#111827

Muted:
#6B7280

Borders:
#E5E7EB

Use gradients sparingly.

Create a small custom application logo combining:

- Play button concept
- AI / neural concept

Do not use the default Lovable logo.

==================================================
IMPORTANT FINAL REQUIREMENTS
==================================================

1. Build the complete frontend.
2. Connect it to the existing FastAPI backend.
3. Use real API calls.
4. Do not create mock data as the final implementation.
5. Do not create a new backend.
6. Do not use Supabase.
7. Do not use Firebase.
8. Do not use Tailwind CSS.
9. Do not break the existing backend.
10. Keep API integration isolated in the API layer.
11. Make the UI production-quality.
12. Make every page responsive.
13. Add proper loading, empty, success, and error states.
14. Use Framer Motion for subtle animations.
15. Use Lucide React icons.
16. Use Recharts for meaningful dashboard analytics.
17. Use the actual OpenAPI specification from the FastAPI backend to determine API contracts.

Start by inspecting the backend OpenAPI schema and then build the frontend around the real API.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/9124e43c-780a-41ff-a72f-af4766e31183).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
