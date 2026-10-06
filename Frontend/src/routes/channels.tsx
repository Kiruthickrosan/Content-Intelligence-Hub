import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/layout/Shell";
import { Channels } from "../pages/Channels";
export const Route = createFileRoute("/channels")({
  head: () => ({
    meta: [
      { title: "Channels — YouTube Q&A" },
      { name: "description", content: "Manage YouTube channels in your knowledge base." },
      { property: "og:title", content: "Channels — YouTube Q&A" },
      { property: "og:description", content: "Manage YouTube channels in your knowledge base." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <Shell>
      <Channels />
    </Shell>
  ),
});
