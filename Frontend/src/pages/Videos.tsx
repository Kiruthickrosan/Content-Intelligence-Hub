import { Filter, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearch } from "@tanstack/react-router";
import { api } from "../api";
import type { Channel, Video, VideoStatus } from "../api/types";
import { Intro, Empty, ErrorBox, Skeleton } from "../components/common/UI";
import { VideoList } from "../components/videos/VideoList";
const statuses: VideoStatus[] = [
  "pending",
  "downloading",
  "transcribing",
  "indexing",
  "completed",
  "failed",
];
export function Videos() {
  const q = useSearch({ strict: false }) as { channel?: number },
    [channels, setChannels] = useState<Channel[]>([]),
    [videos, setVideos] = useState<Video[]>([]),
    [total, setTotal] = useState(0),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [status, setStatus] = useState<VideoStatus | "">(""),
    [channel, setChannel] = useState(q.channel ? String(q.channel) : ""),
    [sort, setSort] = useState("date"),
    [page, setPage] = useState(0);
  const load = () => {
    setLoading(true);
    Promise.all([
      api.channels(),
      api.videos({
        limit: 20,
        offset: page * 20,
        ...(channel ? { channel_id: +channel } : {}),
        ...(status ? { status } : {}),
      }),
    ])
      .then(([c, v]) => {
        setChannels(c.channels);
        setVideos(v.videos);
        setTotal(v.total);
        setError("");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, [channel, status, page]);
  const shown = useMemo(
    () =>
      videos
        .filter((v) => v.title.toLowerCase().includes(query.toLowerCase()))
        .sort((a, b) =>
          sort === "title"
            ? a.title.localeCompare(b.title)
            : sort === "status"
              ? a.status.localeCompare(b.status)
              : +new Date(b.created_at) - +new Date(a.created_at),
        ),
    [videos, query, sort],
  );
  return (
    <>
      <Intro
        eyebrow="Video library"
        title="Videos"
        subtitle="Search, filter, and monitor every video in your knowledge base."
      />
      <section className="filterbar">
        <div className="searchbox">
          <Search />
          <input
            placeholder="Search videos…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <label className="select-wrap">
          <Filter />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as any);
              setPage(0);
            }}
          >
            <option value="">All statuses</option>
            {statuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="select-wrap">
          <SlidersHorizontal />
          <select
            value={channel}
            onChange={(e) => {
              setChannel(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All channels</option>
            {channels.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <select className="sort-select" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="date">Newest first</option>
          <option value="title">Title A–Z</option>
          <option value="status">Status</option>
        </select>
      </section>
      <section className="panel library-panel">
        <div className="panel-head">
          <h2>{total} videos</h2>
        </div>
        {loading ? (
          <Skeleton />
        ) : error ? (
          <ErrorBox message={error} retry={load} />
        ) : shown.length ? (
          <>
            <VideoList videos={shown} channels={channels} />
            <div className="pagination">
              <button
                className="btn btn-secondary"
                disabled={!page}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {page + 1} of {Math.max(1, Math.ceil(total / 20))}
              </span>
              <button
                className="btn btn-secondary"
                disabled={(page + 1) * 20 >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </>
        ) : (
          <Empty title="No matching videos" text="Try adjusting your filters or sync a channel." />
        )}
      </section>
    </>
  );
}
