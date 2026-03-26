"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { getVideos, uploadVideo } from "@/lib/api";
import { Upload, Play, X, Loader2 } from "lucide-react";

interface VideoItem {
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
      {/* Header + upload */}
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
              className="absolute -top-10 right-0 text-white hover:text-gray-300 flex items-center gap-1 text-sm"
            >
              <X className="w-5 h-5" /> Lukk
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="broker-card h-40 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Video grid */}
      {!isLoading && videos.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video, idx) => {
            const name = displayName(video.name, idx);
            const hasUrl = !!video.url;
            return (
              <div key={idx} className="broker-card space-y-3">
                {/* Thumbnail / play area */}
                <div
                  className={`w-full h-28 bg-[#EDE8E3] rounded-lg flex items-center justify-center relative overflow-hidden ${hasUrl ? "cursor-pointer group" : ""}`}
                  onClick={() => hasUrl && setPlayingUrl(video.url as string)}
                >
                  <Play className={`w-10 h-10 text-[#8A7F74] ${hasUrl ? "group-hover:text-[#4A6FA5] transition-colors" : ""}`} fill="currentColor" />
                  {hasUrl && (
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors rounded-lg" />
                  )}
                </div>
                <p className="text-sm font-medium text-[#2C3E50] truncate" title={name}>{name}</p>
                <div className="flex items-center justify-between text-xs text-[#8A7F74]">
                  <span>{fmtSize(video.size)}</span>
                  <span>{fmtDate(video.last_modified)}</span>
                </div>
                <div className="flex gap-2">
                  {hasUrl && (
                    <button
                      onClick={() => setPlayingUrl(video.url as string)}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2C3E50] text-white text-xs font-medium hover:bg-[#3d5166] transition-colors"
                    >
                      <Play className="w-3 h-3" fill="currentColor" /> Spill av
                    </button>
                  )}
                  {hasUrl && (
                    <a
                      href={video.url as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg bg-[#EDE8E3] text-[#8A7F74] text-xs font-medium hover:bg-[#DDD8D3] transition-colors"
                    >
                      Åpne
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!isLoading && videos.length === 0 && (
        <div className="broker-card text-center py-16">
          <Play className="w-10 h-10 text-[#EDE8E3] mx-auto mb-3" />
          <p className="text-sm font-medium text-[#2C3E50]">Ingen videoer lastet opp ennå</p>
          <p className="text-xs text-[#8A7F74] mt-1">Klikk «Last opp video» for å legge til den første.</p>
        </div>
      )}
    </div>
  );
}
