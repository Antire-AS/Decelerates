"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Dot,
} from "recharts";
import type { AltmanTrendPoint } from "@/lib/api-types";
import { getOrgAltmanHistory } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface Props {
  orgnr: string;
}

// Altman 2000 zone thresholds (duplicated from AltmanZSection — kept local
// to this file so the chart has no cross-component dependency).
const Z_DISTRESS_TOP = 1.10;
const Z_GREY_TOP = 2.60;

// Fixed Y-axis ceiling. Most companies land in [0, 4]; clipping visual
// outliers keeps the zone bands legible. If a company scores above 4 the
// dot still shows at the top edge and the tooltip reveals the real value.
const Y_MAX = 4;

const ZONE_COLOR: Record<AltmanTrendPoint["zone"], string> = {
  safe: "#22c55e",
  grey: "#eab308",
  distress: "#ef4444",
};

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: AltmanTrendPoint;
}

function ZoneDot(props: DotProps) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined || !payload) return null;
  return <Dot cx={cx} cy={cy} r={4} fill={ZONE_COLOR[payload.zone]} stroke="white" strokeWidth={1.5} />;
}

export default function AltmanTrendChart({ orgnr }: Props) {
  const T = useT();
  const [points, setPoints] = useState<AltmanTrendPoint[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getOrgAltmanHistory(orgnr)
      .then((res) => {
        if (!cancelled) setPoints(res.points ?? []);
      })
      .catch((e: Error) => {
        if (!cancelled) setErr(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [orgnr]);

  if (err) return null; // Silent fail — the point-in-time panel still shows above.
  if (points === null) return null; // Loading.
  if (points.length < 2) return null; // A line chart of one point isn't useful.

  return (
    <div className="mt-4 pt-3 border-t border-muted">
      <h4 className="text-xs font-semibold text-foreground mb-1.5">
        {T("Historisk Z″-utvikling")}
      </h4>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
            <XAxis dataKey="year" tick={{ fontSize: 10 }} />
            <YAxis
              domain={[0, Y_MAX]}
              tick={{ fontSize: 10 }}
              tickCount={5}
              allowDataOverflow
            />
            {/* Zone boundaries: anything below 1.10 is distress, 1.10–2.60 grey,
                above 2.60 safe. ReferenceLine makes the context visible at a
                glance without a separate legend. */}
            <ReferenceLine
              y={Z_DISTRESS_TOP}
              stroke={ZONE_COLOR.distress}
              strokeDasharray="4 4"
              label={{
                value: String(Z_DISTRESS_TOP),
                position: "right",
                fontSize: 9,
                fill: ZONE_COLOR.distress,
              }}
            />
            <ReferenceLine
              y={Z_GREY_TOP}
              stroke={ZONE_COLOR.safe}
              strokeDasharray="4 4"
              label={{
                value: String(Z_GREY_TOP),
                position: "right",
                fontSize: 9,
                fill: ZONE_COLOR.safe,
              }}
            />
            <Tooltip
              formatter={(v: number) => [v.toFixed(2), "Z″"]}
              labelFormatter={(year) => String(year)}
              contentStyle={{ fontSize: 11 }}
            />
            <Line
              type="monotone"
              dataKey="z_score"
              stroke="#4A6FA5"
              strokeWidth={2}
              dot={<ZoneDot />}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
