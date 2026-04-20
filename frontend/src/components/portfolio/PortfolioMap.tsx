"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Link from "next/link";
import type { PortfolioRiskRow } from "@/lib/api";
import { apiBaseUrl } from "@/lib/api-utils";
import { useRiskConfig, UNKNOWN_BAND } from "@/lib/useRiskConfig";

// Fix default marker icons broken by webpack
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;

function makeIcon(color: string) {
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
  const { bands, bandFor } = useRiskConfig();

  const colorFor = (score?: number | null) => bandFor(score).color;

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
      <div className="flex items-center justify-center h-48 text-xs text-muted-foreground">
        Henter koordinater…
      </div>
    );
  }

  if (!markers.length) return null;

  // Centre map on mean lat/lon
  const centerLat = markers.reduce((s, m) => s + m.lat, 0) / markers.length;
  const centerLon = markers.reduce((s, m) => s + m.lon, 0) / markers.length;

  // Build legend entries from live band config (+ unknown entry)
  const legendEntries = [
    ...bands.map((b) => ({ label: b.label, color: b.color })),
    { label: "Ukjent", color: UNKNOWN_BAND.color },
  ];

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex gap-4 text-xs text-muted-foreground">
        {legendEntries.map(({ label, color }) => (
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
          <Marker key={m.orgnr} position={[m.lat, m.lon]} icon={makeIcon(colorFor(m.risk_score))}>
            <Popup>
              <div className="text-xs space-y-1 min-w-[120px]">
                <p className="font-semibold text-foreground">{m.navn ?? m.orgnr}</p>
                <p className="text-muted-foreground">Risikoscore: {m.risk_score ?? "–"}</p>
                <Link
                  href={`/search/${m.orgnr}`}
                  className="text-primary underline"
                >
                  Åpne profil →
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <p className="text-xs text-muted-foreground">{markers.length} av {rows.length} selskaper har adressedata</p>
    </div>
  );
}
