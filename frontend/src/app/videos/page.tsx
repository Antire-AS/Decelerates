"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { getVideos, uploadVideo } from "@/lib/api";
import { Upload, Play, ExternalLink, Loader2, Video } from "lucide-react";

interface VideoItem {
  filename?: string;
  video_url?: string;
  blob_name?: string;
  thumbnail_url?: string;
  sections?: unknown;
  // legacy fields (upload endpoint)
  name?: string;
  url?: string;
  size?: number;
  last_modified?: string;
  [key: string]: unknown;
}

function fmtSize(bytes?: number) {
  if (!bytes) return "–";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(dateStr?: string) {
  if (!dateStr) return "–";
  return new Date(dateStr).toLocaleDateString("nb-NO", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function displayName(name?: string, idx?: number) {
  if (!name) return `Video ${(idx ?? 0) + 1}`;
  return name.includes("/") ? name.split("/").pop() ?? name : name;
}

export default function VideosPage() {
  const { data: rawVideos, isLoading, mutate } = useSWR<unknown[]>("videos", getVideos);
  const videos = (rawVideos ?? []) as VideoItem[];

  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadVideo(file);
      await mutate();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Opplasting feilet");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Videoer</h1>
          <p className="text-sm text-[#8A7F74] mt-1">Opplastede opplærings- og presentasjonsvideoer</p>
        </div>
        <div>
          <input ref={fileRef} type="file" accept="video/*" className="hidden" onChange={handleUpload} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] transition-colors disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Laster opp…" : "Last opp video"}
          </button>
        </div>
      </div>

      {uploadError && (
        <div className="broker-card border-l-4 border-red-400 text-sm text-red-700">{uploadError}</div>
      )}

      {/* Inline video player modal */}
      {playingUrl && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setPlayingUrl(null)}>
          <div className="relative w-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setPlayingUrl(null)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300 text-sm px-3 py-1 rounded bg-black/40"
            >
              Lukk ×
            </button>
            <video
              src={playingUrl}
              controls
              autoPlay
              className="w-full rounded-xl shadow-2xl max-h-[80vh]"
            />
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 rounded animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Video list */}
      {!isLoading && videos.length > 0 && (
        <div className="broker-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-3 font-medium">Navn</th>
                <th className="text-right pb-3 font-medium hidden sm:table-cell">Størrelse</th>
                <th className="text-right pb-3 font-medium hidden md:table-cell">Dato</th>
                <th className="text-right pb-3 font-medium">Handlinger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {videos.map((video, idx) => {
                const name = video.filename || displayName(video.name, idx);
                const playUrl = video.video_url || video.url;
                const hasUrl = !!playUrl;
                return (
                  <tr key={idx} className="hover:bg-[#F9F7F4] group">
                    <td className="py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-[#EDE8E3] flex items-center justify-center flex-shrink-0">
                          <Video className="w-4 h-4 text-[#8A7F74]" />
                        </div>
                        <span className="font-medium text-[#2C3E50] truncate max-w-[200px] sm:max-w-xs" title={name}>
                          {name}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 text-right text-xs text-[#8A7F74] hidden sm:table-cell">
                      {fmtSize(video.size)}
                    </td>
                    <td className="py-3 text-right text-xs text-[#8A7F74] hidden md:table-cell">
                      {fmtDate(video.last_modified)}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {hasUrl && (
                          <button
                            onClick={() => setPlayingUrl(playUrl as string)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2C3E50] text-white text-xs font-medium hover:bg-[#3d5166] transition-colors"
                          >
                            <Play className="w-3 h-3" fill="currentColor" />
                            Spill av
                          </button>
                        )}
                        {hasUrl && (
                          <a
                            href={playUrl as string}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg text-[#8A7F74] hover:bg-[#EDE8E3] transition-colors"
                            title="Åpne i ny fane"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!isLoading && videos.length === 0 && (
        <div className="broker-card text-center py-16">
          <Video className="w-10 h-10 text-[#EDE8E3] mx-auto mb-3" />
          <p className="text-sm font-medium text-[#2C3E50]">Ingen videoer lastet opp ennå</p>
          <p className="text-xs text-[#8A7F74] mt-1">Klikk «Last opp video» for å legge til den første.</p>
        </div>
      )}
    </div>
  );
}
