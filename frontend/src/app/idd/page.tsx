"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { FileText, Plus, Trash2, ChevronDown, ChevronUp, Loader2, CheckCircle, ChevronRight } from "lucide-react";
import { getOrgIdd, getAllIdd, createOrgIdd, deleteOrgIdd, type IddBehovsanalyse } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const PRODUCTS = [
  "Motorvognforsikring",
  "Næringseiendom",
  "Ansvarsforsikring",
  "Yrkesskadeforsikring",
  "Reiseforsikring",
  "Personforsikring",
  "Cyberforsikring",
  "Styreansvarsforsikring",
  "Varetransportforsikring",
  "Avbruddsforsikring",
];

function fmt(n: number | undefined | null) {
  if (n == null) return "–";
  return new Intl.NumberFormat("nb-NO").format(Math.round(n));
}

function IddCard({ row, onDelete }: { row: IddBehovsanalyse; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const date = row.created_at ? new Date(row.created_at).toLocaleDateString("nb-NO") : "–";

  return (
    <div className="broker-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[#2C3E50]">
            {row.client_name || row.orgnr}
          </p>
          <p className="text-xs text-[#8A7F74] mt-0.5">
            Utarbeidet {date} · {row.created_by_email ?? ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setOpen((v) => !v)}
            className="text-xs text-[#4A6FA5] hover:underline flex items-center gap-1">
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? "Skjul" : "Vis"}
          </button>
          <button onClick={onDelete}
            className="text-red-400 hover:text-red-600">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-4 space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-1">Kontaktperson</p>
              <p className="text-[#2C3E50]">{row.client_contact_name || "–"}</p>
              {row.client_contact_email && (
                <p className="text-xs text-[#8A7F74]">{row.client_contact_email}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-1">Risikoappetitt</p>
              <p className="text-[#2C3E50] capitalize">{row.risk_appetite || "–"}</p>
            </div>
          </div>

          <div>
            <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Risikoforhold</p>
            <div className="flex flex-wrap gap-2">
              {[
                ["Eiendom", row.property_owned],
                ["Ansatte", row.has_employees],
                ["Kjøretøy", row.has_vehicles],
                ["Profesjonsansvar", row.has_professional_liability],
                ["Cyber", row.has_cyber_risk],
              ].map(([label, val]) => (
                <span key={String(label)}
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    val ? "bg-green-100 text-green-700" : "bg-[#EDE8E3] text-[#8A7F74]"
                  }`}>
                  {String(label)}
                </span>
              ))}
            </div>
          </div>

          {(row.recommended_products ?? []).length > 0 && (
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Anbefalte produkter</p>
              <div className="flex flex-wrap gap-1.5">
                {row.recommended_products!.map((p) => (
                  <span key={p} className="text-xs bg-[#F0F4FB] text-[#4A6FA5] border border-[#C5D0E8] px-2 py-0.5 rounded-full">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}

          {row.advisor_notes && (
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-1">Rådgivers notater</p>
              <p className="text-xs text-[#2C3E50] bg-[#F9F7F4] rounded-lg p-2">{row.advisor_notes}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#EDE8E3]">
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-0.5">Vederlagsgrunnlag</p>
              <p className="text-[#2C3E50] capitalize">{row.fee_basis || "–"}</p>
              {row.fee_amount_nok != null && (
                <p className="text-xs text-[#8A7F74]">kr {fmt(row.fee_amount_nok)}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-0.5">Egnethetsvurdering</p>
              <p className="text-xs text-[#2C3E50]">{row.suitability_basis || "–"}</p>
            </div>
          </div>

          {(row.existing_insurance ?? []).length > 0 && (
            <div>
              <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Eksisterende forsikringer</p>
              <div className="space-y-1">
                {row.existing_insurance!.map((e, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-[#2C3E50]">{e.insurer} · {e.product}</span>
                    {e.premium != null && <span className="text-[#8A7F74]">kr {fmt(e.premium)}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NewIddForm({ orgnr, onCreated }: { orgnr: string; onCreated: () => void }) {
  const [loading, setLoading] = useState(false);
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [form, setForm] = useState({
    client_name: "",
    client_contact_name: "",
    client_contact_email: "",
    risk_appetite: "middels",
    property_owned: false,
    has_employees: false,
    has_vehicles: false,
    has_professional_liability: false,
    has_cyber_risk: false,
    annual_revenue_nok: "",
    special_requirements: "",
    recommended_products: [] as string[],
    advisor_notes: "",
    suitability_basis: "",
    fee_basis: "provisjon",
    fee_amount_nok: "",
  });

  const toggleProduct = (p: string) =>
    setForm((f) => ({
      ...f,
      recommended_products: f.recommended_products.includes(p)
        ? f.recommended_products.filter((x) => x !== p)
        : [...f.recommended_products, p],
    }));

  async function submit() {
    setLoading(true); setErr(null);
    try {
      await createOrgIdd(orgnr, {
        ...form,
        annual_revenue_nok: form.annual_revenue_nok ? Number(form.annual_revenue_nok) : undefined,
        fee_amount_nok: form.fee_amount_nok ? Number(form.fee_amount_nok) : undefined,
        existing_insurance: [],
      });
      setOk(true);
      onCreated();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  if (ok) return (
    <div className="broker-card flex items-center gap-2 text-green-700">
      <CheckCircle className="w-4 h-4" />
      <span className="text-sm font-medium">Behovsanalyse lagret.</span>
    </div>
  );

  return (
    <div className="broker-card space-y-4">
      <h3 className="text-sm font-semibold text-[#2C3E50]">Ny behovsanalyse</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          ["client_name", "Selskapsnavn"],
          ["client_contact_name", "Kontaktperson"],
          ["client_contact_email", "E-post kontakt"],
          ["annual_revenue_nok", "Omsetning (NOK)"],
        ].map(([key, label]) => (
          <div key={key}>
            <label className="text-xs text-[#8A7F74] font-medium" htmlFor={`idd-${key}`}>{label}</label>
            <input
              id={`idd-${key}`}
              value={(form as Record<string, unknown>)[key] as string}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]"
            />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="idd-risk-appetite">Risikoappetitt</label>
          <select id="idd-risk-appetite" value={form.risk_appetite}
            onChange={(e) => setForm((f) => ({ ...f, risk_appetite: e.target.value }))}
            className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]">
            <option value="lav">Lav</option>
            <option value="middels">Middels</option>
            <option value="høy">Høy</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="idd-fee-basis">Vederlagsgrunnlag</label>
          <select id="idd-fee-basis" value={form.fee_basis}
            onChange={(e) => setForm((f) => ({ ...f, fee_basis: e.target.value }))}
            className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]">
            <option value="provisjon">Provisjon</option>
            <option value="honorar">Honorar</option>
            <option value="begge">Begge</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-[#8A7F74] font-medium" htmlFor="idd-fee-amount">Honorar (NOK)</label>
          <input id="idd-fee-amount" value={form.fee_amount_nok}
            onChange={(e) => setForm((f) => ({ ...f, fee_amount_nok: e.target.value }))}
            placeholder="0"
            className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]" />
        </div>
      </div>

      <div>
        <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Risikoforhold</p>
        <div className="flex flex-wrap gap-2">
          {[
            ["property_owned", "Eier eiendom"],
            ["has_employees", "Har ansatte"],
            ["has_vehicles", "Har kjøretøy"],
            ["has_professional_liability", "Profesjonsansvar"],
            ["has_cyber_risk", "Cyberrisiko"],
          ].map(([key, label]) => (
            <button key={key}
              onClick={() => setForm((f) => ({ ...f, [key]: !(f as Record<string, unknown>)[key] }))}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                (form as Record<string, unknown>)[key]
                  ? "bg-[#2C3E50] text-white border-[#2C3E50]"
                  : "bg-white text-[#8A7F74] border-[#D4C9B8] hover:border-[#4A6FA5]"
              }`}>{label}</button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-[#8A7F74] font-medium mb-1.5">Anbefalte produkter</p>
        <div className="flex flex-wrap gap-2">
          {PRODUCTS.map((p) => (
            <button key={p} onClick={() => toggleProduct(p)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                form.recommended_products.includes(p)
                  ? "bg-[#4A6FA5] text-white border-[#4A6FA5]"
                  : "bg-white text-[#8A7F74] border-[#D4C9B8] hover:border-[#4A6FA5]"
              }`}>{p}</button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-[#8A7F74] font-medium" htmlFor="idd-suitability-basis">Egnethetsvurdering (IDD § 7-7)</label>
        <textarea id="idd-suitability-basis" value={form.suitability_basis}
          onChange={(e) => setForm((f) => ({ ...f, suitability_basis: e.target.value }))}
          rows={2}
          placeholder="Begrunn hvorfor anbefalte produkter er egnet for kunden…"
          className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5] resize-none" />
      </div>

      <div>
        <label className="text-xs text-[#8A7F74] font-medium" htmlFor="idd-advisor-notes">Rådgivers notater</label>
        <textarea id="idd-advisor-notes" value={form.advisor_notes}
          onChange={(e) => setForm((f) => ({ ...f, advisor_notes: e.target.value }))}
          rows={2}
          className="mt-0.5 w-full text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5] resize-none" />
      </div>

      {err && <p className="text-xs text-red-500">{err}</p>}

      <button onClick={submit} disabled={loading}
        className="px-4 py-2 bg-[#2C3E50] text-white text-sm rounded-lg hover:bg-[#1a252f] disabled:opacity-50 flex items-center gap-2">
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        Lagre behovsanalyse
      </button>
    </div>
  );
}

function IddContent() {
  const searchParams = useSearchParams();
  const orgnr = searchParams.get("orgnr") ?? "";
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { data: rows, isLoading, mutate } = useSWR<IddBehovsanalyse[]>(
    orgnr ? `idd-${orgnr}` : null,
    () => getOrgIdd(orgnr),
  );

  // Firm-wide list when no orgnr is selected (no longer an empty state)
  const { data: allRows, isLoading: allLoading } = useSWR<IddBehovsanalyse[]>(
    !orgnr ? "idd-all" : null,
    () => getAllIdd(100),
  );

  function handleDelete(id: number) {
    setDeleteId(id);
  }

  async function performDelete(id: number) {
    await deleteOrgIdd(orgnr, id);
    mutate();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">IDD Behovsanalyse</h1>
          <p className="text-sm text-[#8A7F74] mt-1">
            Forsikringsformidlingsloven §§ 5-4, 7-1 til 7-10 · Finanstilsynet rundskriv 9/2019
          </p>
        </div>
        {orgnr && (
          <button onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-[#2C3E50] text-white text-sm rounded-lg hover:bg-[#1a252f]">
            <Plus className="w-4 h-4" />
            Ny analyse
          </button>
        )}
      </div>

      {!orgnr && (
        <>
          {allLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>
          ) : !allRows?.length ? (
            <div className="broker-card text-center py-10">
              <FileText className="w-8 h-8 text-[#8A7F74] mx-auto mb-2" />
              <p className="text-sm text-[#8A7F74]">
                Ingen behovsanalyser registrert ennå. Åpne et selskap fra Selskapsøk og lag en
                behovsanalyse fra CRM-fanen.
              </p>
            </div>
          ) : (
            <div className="broker-card divide-y divide-[#EDE8E3]">
              <p className="text-xs text-[#8A7F74] pb-2 font-medium">
                {allRows.length} behovsanalyser i alle selskaper · Klikk for å se detaljer
              </p>
              {allRows.map((r) => {
                const date = r.created_at ? new Date(r.created_at).toLocaleDateString("nb-NO") : "–";
                return (
                  <Link
                    key={r.id}
                    href={`/idd?orgnr=${r.orgnr}`}
                    className="flex items-center justify-between gap-3 py-2.5 hover:bg-[#F9F7F4] px-1 -mx-1 rounded"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[#2C3E50] truncate">
                        {r.client_name || r.orgnr}
                      </p>
                      <p className="text-xs text-[#8A7F74]">
                        Orgnr {r.orgnr} · utarbeidet {date}
                        {r.recommended_products?.length ? ` · ${r.recommended_products.length} produkter` : ""}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#C4BDB4] flex-shrink-0" />
                  </Link>
                );
              })}
            </div>
          )}
        </>
      )}

      {orgnr && (
        <>
          {showForm && (
            <NewIddForm orgnr={orgnr} onCreated={() => { mutate(); setShowForm(false); }} />
          )}

          {isLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>
          ) : !rows?.length ? (
            <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">
              Ingen behovsanalyser registrert for dette selskapet ennå.
            </div>
          ) : (
            <div className="space-y-3">
              {rows.map((r) => (
                <IddCard key={r.id} row={r} onDelete={() => handleDelete(r.id)} />
              ))}
            </div>
          )}

          {/* IDD compliance reference */}
          <details className="broker-card">
            <summary className="text-sm font-semibold text-[#2C3E50] cursor-pointer">
              IDD-krav — lovgrunnlag
            </summary>
            <div className="mt-3 space-y-2 text-xs text-[#8A7F74]">
              <p><strong className="text-[#2C3E50]">§ 5-4</strong> — Plikt til å yte god rådgivning basert på kundens behov og situasjon.</p>
              <p><strong className="text-[#2C3E50]">§ 7-1 til 7-10</strong> — Informasjonskrav ved distribusjon: IPID, vederlagsinformasjon, rådgivningsdokument.</p>
              <p><strong className="text-[#2C3E50]">Rundskriv 9/2019</strong> — Finanstilsynets forventninger til behovsanalyse: kartlegging av eksisterende dekning, risikoforhold, økonomi og behov.</p>
              <p><strong className="text-[#2C3E50]">Vederlagsinformasjon</strong> — Kunden skal informeres om provisjonsgrunnlag og størrelse eller honorarsats før avtale inngås.</p>
            </div>
          </details>
        </>
      )}

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(o) => { if (!o) setDeleteId(null); }}
        title="Slette behovsanalyse?"
        description="Handlingen kan ikke angres."
        confirmLabel="Slett"
        destructive
        onConfirm={() => {
          if (deleteId !== null) performDelete(deleteId);
        }}
      />
    </div>
  );
}

export default function IddPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>}>
      <IddContent />
    </Suspense>
  );
}
