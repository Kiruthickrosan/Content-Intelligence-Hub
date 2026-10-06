import { createFileRoute } from "@tanstack/react-router";
import { AuthPage } from "../pages/AuthPage";
export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — YouTube Q&A" },
      { name: "description", content: "Create your YouTube Q&A workspace account." },
      { property: "og:title", content: "Create account — YouTube Q&A" },
      { property: "og:description", content: "Create your YouTube Q&A workspace account." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => <AuthPage mode="register" />,
});
