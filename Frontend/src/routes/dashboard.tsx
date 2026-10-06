import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/layout/Shell";
import { Dashboard } from "../pages/Dashboard";
export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — YouTube Q&A" },
      { name: "description", content: "Monitor your indexed YouTube knowledge base." },
      { property: "og:title", content: "Dashboard — YouTube Q&A" },
      { property: "og:description", content: "Monitor your indexed YouTube knowledge base." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <Shell>
      <Dashboard />
    </Shell>
  ),
});
