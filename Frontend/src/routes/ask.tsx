import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/layout/Shell";
import { AskAI } from "../pages/AskAI";
export const Route = createFileRoute("/ask")({
  head: () => ({
    meta: [
      { title: "Ask AI — YouTube Q&A" },
      {
        name: "description",
        content: "Ask grounded questions across your indexed YouTube videos.",
      },
      { property: "og:title", content: "Ask AI — YouTube Q&A" },
      {
        property: "og:description",
        content: "Ask grounded questions across your indexed YouTube videos.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <Shell>
      <AskAI />
    </Shell>
  ),
});
