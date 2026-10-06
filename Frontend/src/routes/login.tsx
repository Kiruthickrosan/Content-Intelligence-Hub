import { createFileRoute } from "@tanstack/react-router";
import { AuthPage } from "../pages/AuthPage";
export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — YouTube Q&A" },
      { name: "description", content: "Sign in to your YouTube Q&A workspace." },
      { property: "og:title", content: "Sign in — YouTube Q&A" },
      { property: "og:description", content: "Sign in to your YouTube Q&A workspace." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => <AuthPage mode="login" />,
});
