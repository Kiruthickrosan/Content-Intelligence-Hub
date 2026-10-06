import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/layout/Shell";
import { VideoDetails } from "../pages/VideoDetails";
export const Route = createFileRoute("/videos/$videoId")({
  head: () => ({
    meta: [
      { title: "Video details — YouTube Q&A" },
      { name: "description", content: "View processing and source details for an indexed video." },
      { property: "og:title", content: "Video details — YouTube Q&A" },
      {
        property: "og:description",
        content: "View processing and source details for an indexed video.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});
function Page() {
  const { videoId } = Route.useParams();
  return (
    <Shell>
      <VideoDetails id={Number(videoId)} />
    </Shell>
  );
}
