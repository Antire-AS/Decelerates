"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Link from "next/link";
import type { PortfolioRiskRow } from "@/lib/api";
import { apiBaseUrl } from "@/lib/api-utils";

// Fix default marker icons broken by webpack
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;

function riskColor(score?: number): string {
  if (score == null) return "#C4BDB4";
  if (score <= 3) return "#27AE60";
  if (score <= 7) return "#C8A951";
  return "#C0392B";
}

function makeIcon(score?: number) {
  const color = riskColor(score);
  return L.divIcon({
    className: "",
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 1px 3px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
}

interface MarkerData {
  orgnr: string;
  navn?: string;
  risk_score?: number;
  lat: number;
  lon: number;
}

interface Props {
  rows: PortfolioRiskRow[];
}

export default function PortfolioMap({ rows }: Props) {
  const [markers, setMarkers] = useState<MarkerData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!rows.length) { setLoading(false); return; }

    const BASE = apiBaseUrl("absolute");

    async function fetchOne(row: PortfolioRiskRow): Promise<MarkerData | null> {
      try {
        const res = await fetch(`${BASE}/org/${row.orgnr}/koordinater`);
        if (!res.ok) return null;
        const data = await res.json();
        const coords = data?.coordinates;
        if (!coords?.lat || !coords?.lon) return null;
        return { orgnr: row.orgnr, navn: row.navn, risk_score: row.risk_score, lat: coords.lat, lon: coords.lon };
      } catch {
        return null;
      }
    }

    setLoading(true);
    Promise.all(rows.map(fetchOne)).then((results) => {
      setMarkers(results.filter((r): r is MarkerData => r !== null));
      setLoading(false);
    });
  }, [rows]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-xs text-[#8A7F74]">
        Henter koordinater…
      </div>
    );
  }

  if (!markers.length) return null;

  // Centre map on mean lat/lon
  const centerLat = markers.reduce((s, m) => s + m.lat, 0) / markers.length;
  const centerLon = markers.reduce((s, m) => s + m.lon, 0) / markers.length;

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex gap-4 text-xs text-[#8A7F74]">
        {[
          { label: "Lav risiko (≤3)", color: "#27AE60" },
          { label: "Moderat (4–7)",   color: "#C8A951" },
          { label: "Høy (≥8)",        color: "#C0392B" },
          { label: "Ukjent",          color: "#C4BDB4" },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full border border-white shadow-sm" style={{ background: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>

      <MapContainer
        center={[centerLat, centerLon]}
        zoom={5}
        scrollWheelZoom={false}
        style={{ height: "380px", width: "100%", borderRadius: "0.75rem", zIndex: 0 }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.map((m) => (
          <Marker key={m.orgnr} position={[m.lat, m.lon]} icon={makeIcon(m.risk_score)}>
            <Popup>
              <div className="text-xs space-y-1 min-w-[120px]">
                <p className="font-semibold text-[#2C3E50]">{m.navn ?? m.orgnr}</p>
                <p className="text-[#8A7F74]">Risikoscore: {m.risk_score ?? "–"}</p>
                <Link
                  href={`/search/${m.orgnr}`}
                  className="text-[#4A6FA5] underline"
                >
                  Åpne profil →
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <p className="text-xs text-[#8A7F74]">{markers.length} av {rows.length} selskaper har adressedata</p>
    </div>
  );
}
