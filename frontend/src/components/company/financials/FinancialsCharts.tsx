"use client";

import { Loader2, Sparkles } from "lucide-react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="broker-card space-y-3">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </div>
  );
}

interface ChartRow { year: number; omsetning: number | null; resultat: number | null; }
interface EqRow   { year: number; ekAndel: number; }
interface DebtRow { year: number; langsiktig: number | null; kortsiktig: number | null; }

interface Props {
  chartData: ChartRow[];
  eqData: EqRow[];
  debtData: DebtRow[];
  commentary: string | null;
  commentaryLoading: boolean;
  commentaryErr: string | null;
  handleCommentary: () => void;
}

export default function FinancialsCharts({
  chartData, eqData, debtData,
  commentary, commentaryLoading, commentaryErr, handleCommentary,
}: Props) {
  const hasRev  = chartData.length > 0;
  const hasEq   = eqData.length > 0;
  const hasDebt = debtData.length > 0;

  if (!hasRev && !hasDebt && !hasEq) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {hasRev && (
        <Section title="Omsetning og resultat (MNOK)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => `${v} MNOK`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="omsetning" name="Omsetning" fill="#4A6FA5" />
              <Bar dataKey="resultat" name="Nettoresultat" fill="#2C3E50" />
            </BarChart>
          </ResponsiveContainer>
        </Section>
      )}
      {hasEq && (
        <Section title="Egenkapitalandel (%)">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={eqData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} unit="%" />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Line type="monotone" dataKey="ekAndel" name="EK-andel" stroke="#4A6FA5" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Section>
      )}
      {hasDebt && (
        <Section title="Gjeldsstruktur (MNOK)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={debtData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => `${v} MNOK`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="langsiktig" name="Langsiktig gjeld" fill="#C8A951" stackId="a" />
              <Bar dataKey="kortsiktig" name="Kortsiktig gjeld" fill="#E8D5A0" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </Section>
      )}
      <div className="broker-card flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" /> AI-finanskommentar
          </h3>
          <button
            onClick={handleCommentary}
            disabled={commentaryLoading}
            className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
          >
            {commentaryLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            Generer
          </button>
        </div>
        {commentaryErr && <p className="text-xs text-red-600">{commentaryErr}</p>}
        {commentary ? (
          <div className="mt-1 bg-muted rounded-lg p-3 flex-1">
            <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">{commentary}</p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground mt-2">
            Klikk «Generer» for AI-analyse av finansiell trendutvikling.
          </p>
        )}
      </div>
    </div>
  );
}
