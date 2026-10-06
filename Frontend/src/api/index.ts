import { request } from "./client";
import type { AskResponse, Channel, Video, VideoStatus, User } from "./types";
export const api = {
  register: (b: { username: string; email: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(b) }, false),
  login: (b: { username: string; password: string }) =>
    request<{ access_token: string }>(
      "/auth/login",
      {
        method: "POST",
        body: new URLSearchParams({
          username: b.username,
          password: b.password,
        }),
      },
      false,
    ),
  health: () => request<{ status: string }>("/health", {}, false),
  channels: () => request<{ channels: Channel[]; total: number }>("/channels"),
  addChannel: (url: string) =>
    request<Channel>("/channels", { method: "POST", body: JSON.stringify({ url }) }),
  syncChannel: (id: number) =>
    request<{ message: string }>(`/channels/${id}/sync`, { method: "POST" }),
  deleteChannel: (id: number) => request<void>(`/channels/${id}`, { method: "DELETE" }),
  videos: (
    p: { channel_id?: number; status?: VideoStatus; limit?: number; offset?: number } = {},
  ) => {
    const q = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
    return request<{ videos: Video[]; total: number }>(`/videos?${q}`);
  },
  video: (id: number) => request<Video>(`/videos/${id}`),
  reprocess: (id: number) =>
    request<{ message: string }>(`/videos/${id}/reprocess`, { method: "POST" }),
  ask: (question: string, channel_id?: number) =>
    request<AskResponse>("/ask", {
      method: "POST",
      body: JSON.stringify({ question, ...(channel_id ? { channel_id } : {}) }),
    }),
};
