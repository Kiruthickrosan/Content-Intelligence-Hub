import { createFileRoute, redirect } from "@tanstack/react-router";

// No head() here: the home route inherits title/description/og/twitter from
// __root.tsx, and ships no og:image so serve-time hosting can inject the
// project's social preview (explicit og:image or latest screenshot).
export const Route = createFileRoute("/")({
  beforeLoad: () => { throw redirect({ to: "/dashboard" }); },
  head: () => ({ meta: [
    { title: "YouTube Q&A — Your video knowledge base" },
    { name: "description", content: "Search and ask questions across your indexed YouTube knowledge base." },
    { property: "og:title", content: "YouTube Q&A — Your video knowledge base" },
    { property: "og:description", content: "Search and ask questions across your indexed YouTube knowledge base." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ]}),
});
