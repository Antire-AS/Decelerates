"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { getVideos, uploadVideo } from "@/lib/api";
import { Upload, Play, ExternalLink, Loader2, Video, BookOpen } from "lucide-react";

interface Chapter {
  title: string;
  start: number; // seconds
  end?: number;
}

interface VideoItem {
  filename?: string;
  video_url?: string;
  blob_name?: string;
  thumbnail_url?: string;
  subtitle_url?: string;
  sections?: Chapter[] | unknown;
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

function fmtTime(secs: number) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function displayName(name?: string, idx?: number) {
  if (!name) return `Video ${(idx ?? 0) + 1}`;
  return name.includes("/") ? name.split("/").pop() ?? name : name;
}

function parseChapters(sections: unknown): Chapter[] {
  if (!Array.isArray(sections)) return [];
  return sections.filter((s): s is Chapter =>
    typeof s === "object" && s !== null && "title" in s && "start" in s,
  );
}

export default function VideosPage() {
  const { data: rawVideos, isLoading, mutate } = useSWR<unknown[]>("videos", getVideos);
  const videos = (rawVideos ?? []) as VideoItem[];

  const [playingVideo, setPlayingVideo] = useState<VideoItem | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setUploadError(null);
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

  function seekTo(secs: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = secs;
      videoRef.current.play();
    }
  }

  const chapters = playingVideo ? parseChapters(playingVideo.sections) : [];
  const playUrl = playingVideo?.video_url || playingVideo?.url;

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
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] disabled:opacity-50">
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Laster opp…" : "Last opp video"}
          </button>
        </div>
      </div>

      {uploadError && (
        <div className="broker-card border-l-4 border-red-400 text-sm text-red-700">{uploadError}</div>
      )}

      {/* Video player modal */}
      {playingVideo && playUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setPlayingVideo(null)}>
          <div className="relative w-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setPlayingVideo(null)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300 text-sm px-3 py-1 rounded bg-black/40">
              Lukk ×
            </button>

            <video
              ref={videoRef}
              src={playUrl as string}
              controls
              autoPlay
              className="w-full rounded-xl shadow-2xl max-h-[65vh]"
            >
              {playingVideo.subtitle_url && (
                <track kind="subtitles" src={playingVideo.subtitle_url as string} srcLang="no" label="Norsk" default />
              )}
            </video>

            {/* Chapter navigation */}
            {chapters.length > 0 && (
              <div className="mt-3 bg-black/60 rounded-xl p-3">
                <p className="text-xs font-semibold text-white mb-2 flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" /> Kapitler
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                  {chapters.map((ch, i) => (
                    <button key={i} onClick={() => seekTo(ch.start)}
                      className="text-left px-2.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs transition-colors">
                      <span className="text-white/50 mr-1.5">{fmtTime(ch.start)}</span>
                      {ch.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="h-12 rounded animate-pulse bg-[#EDE8E3]" />)}
        </div>
      )}

      {/* Video list */}
      {!isLoading && videos.length > 0 && (
        <div className="broker-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-3 font-medium">Navn</th>
                <th className="text-center pb-3 font-medium hidden sm:table-cell">Kapitler</th>
                <th className="text-right pb-3 font-medium hidden sm:table-cell">Størrelse</th>
                <th className="text-right pb-3 font-medium hidden md:table-cell">Dato</th>
                <th className="text-right pb-3 font-medium">Handlinger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {videos.map((video, idx) => {
                const name = video.filename || displayName(video.name, idx);
                const hasUrl = !!(video.video_url || video.url);
                const chs = parseChapters(video.sections);
                return (
                  <tr key={idx} className="hover:bg-[#F9F7F4] group">
                    <td className="py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-[#EDE8E3] flex items-center justify-center flex-shrink-0">
                          <Video className="w-4 h-4 text-[#8A7F74]" />
                        </div>
                        <div>
                          <span className="font-medium text-[#2C3E50] truncate max-w-[160px] sm:max-w-xs block" title={name}>
                            {name}
                          </span>
                          {video.subtitle_url && (
                            <span className="text-xs text-[#8A7F74]">Undertekster tilgjengelig</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 text-center text-xs text-[#8A7F74] hidden sm:table-cell">
                      {chs.length > 0 ? `${chs.length} kap.` : "–"}
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
                          <button onClick={() => setPlayingVideo(video)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2C3E50] text-white text-xs font-medium hover:bg-[#3d5166]">
                            <Play className="w-3 h-3" fill="currentColor" />
                            Spill av
                          </button>
                        )}
                        {hasUrl && (
                          <a href={(video.video_url || video.url) as string} target="_blank" rel="noopener noreferrer"
                            className="p-1.5 rounded-lg text-[#8A7F74] hover:bg-[#EDE8E3]" title="Åpne i ny fane">
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
