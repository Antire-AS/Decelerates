"use client";

import useSWR from "swr";
import { getVideos } from "@/lib/api";

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
  return new Date(dateStr).toLocaleDateString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function VideosPage() {
  const { data: rawVideos, isLoading } = useSWR<unknown[]>("videos", getVideos);
  const videos = (rawVideos ?? []) as VideoItem[];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Videoer</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Opplastede opplærings- og presentasjonsvideoer
        </p>
      </div>

      {/* Placeholder */}
      <div className="broker-card border-l-4 border-[#C8A951]">
        <p className="text-sm font-semibold text-[#2C3E50] mb-1">Full implementasjon kommer</p>
        <p className="text-sm text-[#8A7F74]">
          Videofanen vil støtte opplasting av nye videoer, innebygd avspilling direkte i
          nettleseren, kategorisering med tagger, og deling av videolenker med kunder.
          Videoer lagres i Azure Blob Storage.
        </p>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="broker-card h-36 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Video grid */}
      {!isLoading && videos.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map((video, idx) => {
            const name = video.name ?? `Video ${idx + 1}`;
            const displayName = name.includes("/") ? name.split("/").pop() ?? name : name;
            return (
              <div key={idx} className="broker-card space-y-2">
                {/* Thumbnail placeholder */}
                <div className="w-full h-24 bg-[#EDE8E3] rounded-lg flex items-center justify-center">
                  <svg
                    className="w-10 h-10 text-[#8A7F74]"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-[#2C3E50] truncate" title={displayName}>
                  {displayName}
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#8A7F74]">{fmtSize(video.size)}</span>
                  <span className="text-xs text-[#8A7F74]">{fmtDate(video.last_modified)}</span>
                </div>
                {video.url && (
                  <a
                    href={video.url as string}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full text-center px-3 py-1.5 rounded-lg bg-[#2C3E50] text-white text-xs font-medium hover:bg-[#3d5166] transition-colors"
                  >
                    Åpne video
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!isLoading && videos.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen videoer lastet opp ennå</p>
          <p className="text-xs text-[#8A7F74] mt-1">
            Videoer lastes opp via API-et og lagres i Azure Blob Storage.
          </p>
        </div>
      )}
    </div>
  );
}
