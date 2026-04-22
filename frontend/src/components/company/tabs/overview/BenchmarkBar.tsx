"use client";

/**
 * Small horizontal overlay that places a company's ratio onto an industry
 * reference scale. Two display modes:
 *
 *   1. Range mode — pass `rangeMin` + `rangeMax`. The bar shades the "typical"
 *      NACE range (green strip) and drops a dot at the company's value.
 *      Used alongside SSB NACE_BENCHMARKS rows (hardcoded typical ranges).
 *
 *   2. Peer mode — pass `peerAvg`. The bar shows the peer average as a
 *      vertical tick; the dot still marks the company. Used alongside
 *      /org/{orgnr}/peer-benchmark rows (live database peers).
 *
 * The scale auto-expands so both the company value and the reference(s)
 * always fit with a small margin on each side — no clipping, no guesses
 * about absolute ratio magnitudes.
 */

interface Props {
  value: number | null | undefined;
  rangeMin?: number | null;
  rangeMax?: number | null;
  peerAvg?: number | null;
  format: (n: number) => string;
}

// Pad the auto-scale so the dot+ticks never touch the track edges.
const SCALE_PADDING = 0.15;

function buildScale(values: number[]): { min: number; max: number } {
  const finite = values.filter((v) => Number.isFinite(v));
  const raw_min = Math.min(...finite, 0);
  const raw_max = Math.max(...finite, 0);
  // If everything collapses to a single point, give ourselves a visible band.
  if (raw_min === raw_max) {
    const magnitude = Math.abs(raw_min) || 1;
    return { min: raw_min - magnitude * 0.5, max: raw_max + magnitude * 0.5 };
  }
  const span = raw_max - raw_min;
  return { min: raw_min - span * SCALE_PADDING, max: raw_max + span * SCALE_PADDING };
}

function pct(value: number, scale: { min: number; max: number }): number {
  return ((value - scale.min) / (scale.max - scale.min)) * 100;
}

export default function BenchmarkBar({ value, rangeMin, rangeMax, peerAvg, format }: Props) {
  if (value == null || !Number.isFinite(value)) return null;

  const refs: number[] = [value];
  if (rangeMin != null) refs.push(rangeMin);
  if (rangeMax != null) refs.push(rangeMax);
  if (peerAvg != null) refs.push(peerAvg);
  const scale = buildScale(refs);

  const hasRange = rangeMin != null && rangeMax != null;
  const inRange = hasRange ? value >= (rangeMin as number) && value <= (rangeMax as number) : null;

  return (
    <div className="w-full">
      <div className="relative h-2 rounded-full bg-muted overflow-visible">
        {hasRange && (
          <div
            className="absolute top-0 h-full bg-green-200 rounded-sm"
            style={{
              left: `${pct(rangeMin as number, scale)}%`,
              width: `${pct(rangeMax as number, scale) - pct(rangeMin as number, scale)}%`,
            }}
            aria-hidden
          />
        )}
        {peerAvg != null && (
          <div
            className="absolute top-[-2px] h-[calc(100%+4px)] w-[2px] bg-foreground/60"
            style={{ left: `calc(${pct(peerAvg, scale)}% - 1px)` }}
            aria-hidden
            title={`Peer-snitt ${format(peerAvg)}`}
          />
        )}
        <div
          className={`absolute top-[-3px] h-[14px] w-[14px] rounded-full border-2 border-white shadow-sm ${
            inRange === false ? "bg-red-500" : inRange === true ? "bg-green-600" : "bg-primary"
          }`}
          style={{ left: `calc(${pct(value, scale)}% - 7px)` }}
          aria-label={`Company value: ${format(value)}`}
          title={format(value)}
        />
      </div>
      {hasRange && (
        <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
          <span>{format(rangeMin as number)}</span>
          <span>{format(rangeMax as number)}</span>
        </div>
      )}
    </div>
  );
}
