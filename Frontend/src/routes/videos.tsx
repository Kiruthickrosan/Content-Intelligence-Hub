import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/layout/Shell";
import { Videos } from "../pages/Videos";
export const Route = createFileRoute("/videos")({
  validateSearch: (s: Record<string, unknown>) => ({
    channel: s["channel"] ? Number(s["channel"]) : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Videos — YouTube Q&A" },
      { name: "description", content: "Search and monitor your indexed YouTube videos." },
      { property: "og:title", content: "Videos — YouTube Q&A" },
      { property: "og:description", content: "Search and monitor your indexed YouTube videos." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <Shell>
      <Videos />
    </Shell>
  ),
});
