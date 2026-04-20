"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { getVideos, uploadVideo } from "@/lib/api";
import { Upload, Play, Loader2, Video, BookOpen, Clock } from "lucide-react";

interface Chapter {
  title: string;
  start: number; // seconds (normalised from start_seconds or start)
  end?: number;
}

interface VideoItem {
  filename?: string;
  video_url?: string;
  blob_name?: string;
  thumbnail_url?: string;
  subtitle_url?: string;
  sections?: unknown;
  name?: string;
  url?: string;
  size?: number;
  last_modified?: string;
  [key: string]: unknown;
}

function fmtTime(secs: number) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function displayName(v: VideoItem, idx: number) {
  return v.filename || v.name || `Video ${idx + 1}`;
}

// Backend stores chapters with start_seconds; normalise to start
function parseChapters(sections: unknown): Chapter[] {
  if (!Array.isArray(sections)) return [];
  return sections
    .filter((s): s is Record<string, unknown> =>
      typeof s === "object" && s !== null && "title" in s &&
      ("start" in s || "start_seconds" in s),
    )
    .map((s) => ({
      title: String(s.title),
      start: Number(s.start ?? s.start_seconds ?? 0),
      end: s.end != null ? Number(s.end) : undefined,
    }));
}

export default function VideosPanel() {
  const { data: rawVideos, isLoading, mutate } = useSWR<unknown[]>("videos", getVideos);
  const videos = (rawVideos ?? []) as VideoItem[];

  const [activeIdx, setActiveIdx] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const activeVideo = videos[activeIdx] ?? null;
  const chapters = activeVideo ? parseChapters(activeVideo.sections) : [];
  const playUrl = activeVideo?.video_url || activeVideo?.url;

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
      void videoRef.current.play();
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Kursvideoer</h1>
          <p className="text-sm text-muted-foreground mt-1">Opplærings- og presentasjonsvideoer for meglere</p>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept="video/*" className="hidden" onChange={handleUpload} />
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-foreground text-sm font-medium hover:bg-muted"
          >
            <Upload className="w-4 h-4" />
            Last opp video
          </button>
        </div>
      </div>

      {/* Upload panel */}
      {showUpload && (
        <div className="broker-card space-y-3">
          <p className="text-sm font-medium text-foreground">Last opp ny video</p>
          {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Laster opp…" : "Velg fil"}
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}

      {!isLoading && videos.length === 0 && (
        <div className="broker-card text-center py-16">
          <Video className="w-10 h-10 text-muted mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground">Ingen videoer lastet opp ennå</p>
        </div>
      )}

      {/* Main layout: sidebar + player */}
      {!isLoading && videos.length > 0 && (
        <div className="flex gap-4 items-start">

          {/* ── Left: video list ─────────────────────────── */}
          <div className="w-72 flex-shrink-0 space-y-2">
            {videos.map((v, idx) => {
              const chs = parseChapters(v.sections);
              const isActive = idx === activeIdx;
              return (
                <button
                  key={idx}
                  onClick={() => setActiveIdx(idx)}
                  className={`w-full text-left rounded-xl border p-3 transition-colors ${
                    isActive
                      ? "border-primary bg-accent"
                      : "border-border bg-card hover:bg-muted"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      isActive ? "bg-primary" : "bg-muted"
                    }`}>
                      <Play className={`w-3 h-3 ${isActive ? "text-white" : "text-muted-foreground"}`} fill="currentColor" />
                    </div>
                    <div className="min-w-0">
                      <p className={`text-sm font-medium leading-snug ${isActive ? "text-primary" : "text-foreground"}`}>
                        {displayName(v, idx)}
                      </p>
                      {chs.length > 0 && (
                        <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                          <BookOpen className="w-3 h-3" />
                          {chs.length} kapitler
                        </p>
                      )}
                      {isActive && <p className="text-xs text-primary mt-0.5 font-medium">▶ Spiller nå</p>}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* ── Right: player + chapters ─────────────────── */}
          <div className="flex-1 min-w-0 space-y-4">
            {/* Video title */}
            <div className="broker-card py-3 px-4">
              <h2 className="text-base font-semibold text-foreground">
                {activeVideo ? displayName(activeVideo, activeIdx) : ""}
              </h2>
              {activeVideo?.subtitle_url && (
                <p className="text-xs text-muted-foreground mt-0.5">Undertekster tilgjengelig</p>
              )}
            </div>

            {/* Video player */}
            {playUrl && (
              <div className="rounded-xl overflow-hidden bg-black shadow-lg">
                <video
                  key={playUrl as string}
                  ref={videoRef}
                  src={playUrl as string}
                  controls
                  className="w-full max-h-[480px]"
                  style={{ display: "block" }}
                >
                  {activeVideo?.subtitle_url && (
                    <track
                      kind="subtitles"
                      src={activeVideo.subtitle_url as string}
                      srcLang="no"
                      label="Norsk"
                      default
                    />
                  )}
                </video>
              </div>
            )}

            {/* Chapter navigation */}
            {chapters.length > 0 && (
              <div className="broker-card">
                <p className="text-sm font-semibold text-foreground mb-3 flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4" />
                  Kapitler ({chapters.length})
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {chapters.map((ch, i) => (
                    <button
                      key={i}
                      onClick={() => seekTo(ch.start)}
                      className="text-left px-3 py-2 rounded-lg border border-border hover:bg-accent hover:border-primary transition-colors group"
                    >
                      <span className="flex items-center gap-2 text-xs">
                        <Clock className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                        <span className="text-primary font-mono font-medium group-hover:text-primary/80">
                          {fmtTime(ch.start)}
                        </span>
                        <span className="text-foreground truncate">{ch.title}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
