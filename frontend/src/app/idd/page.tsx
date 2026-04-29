"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { FileText, Plus, Trash2, ChevronDown, ChevronUp, Loader2, CheckCircle, ChevronRight } from "lucide-react";
import { getOrgIdd, getAllIdd, createOrgIdd, deleteOrgIdd, type IddBehovsanalyse } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

function RequiredMark() {
  const T = useT();
  return <span className="text-red-500 ml-0.5" aria-label={T("Påkrevd felt")}>*</span>;
}

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
  const T = useT();
  const [open, setOpen] = useState(false);
  const date = row.created_at ? new Date(row.created_at).toLocaleDateString("nb-NO") : "–";

  return (
    <div className="broker-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {row.client_name || row.orgnr}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {T("Utarbeidet")} {date} · {row.created_by_email ?? ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setOpen((v) => !v)}
            className="text-xs text-primary hover:underline flex items-center gap-1">
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? T("Skjul") : T("Vis")}
          </button>
          <button onClick={onDelete}
            className="text-red-400 hover:text-red-600"
            aria-label="Slett behovsanalyse">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-4 space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1">{T("Kontaktperson")}</p>
              <p className="text-foreground">{row.client_contact_name || "–"}</p>
              {row.client_contact_email && (
                <p className="text-xs text-muted-foreground">{row.client_contact_email}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1">{T("Risikoappetitt")}</p>
              <p className="text-foreground capitalize">{row.risk_appetite ? T(row.risk_appetite) : "–"}</p>
            </div>
          </div>

          <div>
            <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Risikoforhold")}</p>
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
                    val ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"
                  }`}>
                  {T(String(label))}
                </span>
              ))}
            </div>
          </div>

          {(row.recommended_products ?? []).length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Anbefalte produkter")}</p>
              <div className="flex flex-wrap gap-1.5">
                {row.recommended_products!.map((p) => (
                  <span key={p} className="text-xs bg-accent text-primary border border-border px-2 py-0.5 rounded-full">
                    {T(p)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {row.advisor_notes && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1">{T("Rådgivers notater")}</p>
              <p className="text-xs text-foreground bg-muted rounded-lg p-2">{row.advisor_notes}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border">
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-0.5">{T("Vederlagsgrunnlag")}</p>
              <p className="text-foreground capitalize">{row.fee_basis ? T(row.fee_basis) : "–"}</p>
              {row.fee_amount_nok != null && (
                <p className="text-xs text-muted-foreground">kr {fmt(row.fee_amount_nok)}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-0.5">{T("Egnethetsvurdering")}</p>
              <p className="text-xs text-foreground">{row.suitability_basis || "–"}</p>
            </div>
          </div>

          {(row.existing_insurance ?? []).length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Eksisterende forsikringer")}</p>
              <div className="space-y-1">
                {row.existing_insurance!.map((e, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-foreground">{e.insurer} · {e.product}</span>
                    {e.premium != null && <span className="text-muted-foreground">kr {fmt(e.premium)}</span>}
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
  const T = useT();
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
      <span className="text-sm font-medium">{T("Behovsanalyse lagret.")}</span>
    </div>
  );

  const fields: [string, string, boolean][] = [
    ["client_name", T("Selskapsnavn"), false],
    ["client_contact_name", T("Kontaktperson"), true],
    ["client_contact_email", T("E-post kontakt"), false],
    ["annual_revenue_nok", T("Omsetning (NOK)"), false],
  ];

  const riskFields: [string, string][] = [
    ["property_owned", T("Eier eiendom")],
    ["has_employees", T("Har ansatte")],
    ["has_vehicles", T("Har kjøretøy")],
    ["has_professional_liability", T("Profesjonsansvar")],
    ["has_cyber_risk", T("Cyberrisiko")],
  ];

  return (
    <div className="broker-card space-y-4">
      <h3 className="text-sm font-semibold text-foreground">{T("Ny behovsanalyse")}</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {fields.map(([key, label, required]) => (
          <div key={key}>
            <label className="text-xs text-muted-foreground font-medium" htmlFor={`idd-${key}`}>
              {label}
              {required && <RequiredMark />}
            </label>
            <input
              id={`idd-${key}`}
              value={(form as Record<string, unknown>)[key] as string}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              required={required}
              aria-describedby={required ? `idd-${key}-hint` : undefined}
              className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {key === "client_contact_name" && (
              <p id="idd-client_contact_name-hint" className="text-[10px] text-muted-foreground mt-0.5">
                {T("Navn på kontaktperson hos kunden.")}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="idd-risk-appetite">{T("Risikoappetitt")}</label>
          <select id="idd-risk-appetite" value={form.risk_appetite}
            onChange={(e) => setForm((f) => ({ ...f, risk_appetite: e.target.value }))}
            className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring">
            <option value="lav">{T("lav")}</option>
            <option value="middels">{T("middels")}</option>
            <option value="høy">{T("høy")}</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="idd-fee-basis">{T("Vederlagsgrunnlag")}</label>
          <select id="idd-fee-basis" value={form.fee_basis}
            onChange={(e) => setForm((f) => ({ ...f, fee_basis: e.target.value }))}
            className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring">
            <option value="provisjon">{T("provisjon")}</option>
            <option value="honorar">{T("honorar")}</option>
            <option value="begge">{T("begge")}</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground font-medium" htmlFor="idd-fee-amount">{T("Honorar (NOK)")}</label>
          <input id="idd-fee-amount" value={form.fee_amount_nok}
            onChange={(e) => setForm((f) => ({ ...f, fee_amount_nok: e.target.value }))}
            placeholder="0"
            className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Risikoforhold")}</p>
        <div className="flex flex-wrap gap-2">
          {riskFields.map(([key, label]) => (
            <button key={key}
              onClick={() => setForm((f) => ({ ...f, [key]: !(f as Record<string, unknown>)[key] }))}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                (form as Record<string, unknown>)[key]
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:border-primary"
              }`}>{label}</button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground font-medium mb-1.5">{T("Anbefalte produkter")}</p>
        <div className="flex flex-wrap gap-2">
          {PRODUCTS.map((p) => (
            <button key={p} onClick={() => toggleProduct(p)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                form.recommended_products.includes(p)
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:border-primary"
              }`}>{T(p)}</button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-muted-foreground font-medium" htmlFor="idd-suitability-basis">
          {T("Egnethetsvurdering (IDD § 7-7)")}<RequiredMark />
        </label>
        <textarea id="idd-suitability-basis" value={form.suitability_basis}
          onChange={(e) => setForm((f) => ({ ...f, suitability_basis: e.target.value }))}
          rows={2}
          required
          aria-describedby="idd-suitability-basis-hint"
          placeholder={T("Begrunn hvorfor anbefalte produkter er egnet for kunden…")}
          className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none" />
        <p id="idd-suitability-basis-hint" className="text-[10px] text-muted-foreground mt-0.5">
          {T("Lovpålagt: forklar kort hvorfor produktene er egnet for denne kunden.")}
        </p>
      </div>

      <div>
        <label className="text-xs text-muted-foreground font-medium" htmlFor="idd-advisor-notes">{T("Rådgivers notater")}</label>
        <textarea id="idd-advisor-notes" value={form.advisor_notes}
          onChange={(e) => setForm((f) => ({ ...f, advisor_notes: e.target.value }))}
          rows={2}
          className="mt-0.5 w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none" />
      </div>

      {err && <p className="text-xs text-red-500">{err}</p>}

      <button onClick={submit} disabled={loading}
        className="px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80 disabled:opacity-50 flex items-center gap-2">
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        {T("Lagre behovsanalyse")}
      </button>
    </div>
  );
}

function IddContent() {
  const T = useT();
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
          <h1 className="text-2xl font-bold text-foreground">{T("IDD Behovsanalyse")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Forsikringsformidlingsloven §§ 5-4, 7-1 til 7-10 · Finanstilsynet rundskriv 9/2019
          </p>
        </div>
        {orgnr && (
          <button onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80">
            <Plus className="w-4 h-4" />
            {T("Ny analyse")}
          </button>
        )}
      </div>

      {!orgnr && (
        <>
          {allLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : !allRows?.length ? (
            <div className="broker-card text-center py-10">
              <FileText className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground mb-3">
                {T("Ingen behovsanalyser ennå.")}
              </p>
              <p className="text-xs text-muted-foreground">
                {T("Gå til")} <a href="/search" className="text-primary underline">{T("Selskapsøk")}</a>{T(", åpne et selskap og velg CRM-fanen for å opprette en behovsanalyse (IDD).")}
              </p>
            </div>
          ) : (
            <div className="broker-card divide-y divide-border">
              <p className="text-xs text-muted-foreground pb-2 font-medium">
                {allRows.length} {T("behovsanalyser i alle selskaper · Klikk for å se detaljer")}
              </p>
              {allRows.map((r) => {
                const date = r.created_at ? new Date(r.created_at).toLocaleDateString("nb-NO") : "–";
                return (
                  <Link
                    key={r.id}
                    href={`/idd?orgnr=${r.orgnr}`}
                    className="flex items-center justify-between gap-3 py-2.5 hover:bg-muted px-1 -mx-1 rounded"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {r.client_name || r.orgnr}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {T("Orgnr")} {r.orgnr} · {T("utarbeidet")} {date}
                        {r.recommended_products?.length ? ` · ${r.recommended_products.length} ${T("produkter")}` : ""}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
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
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : !rows?.length ? (
            <div className="broker-card text-center py-10 text-sm text-muted-foreground">
              {T("Ingen behovsanalyser registrert for dette selskapet ennå.")}
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
            <summary className="text-sm font-semibold text-foreground cursor-pointer">
              {T("IDD-krav — lovgrunnlag")}
            </summary>
            <div className="mt-3 space-y-2 text-xs text-muted-foreground">
              <p><strong className="text-foreground">§ 5-4</strong> — Plikt til å yte god rådgivning basert på kundens behov og situasjon.</p>
              <p><strong className="text-foreground">§ 7-1 til 7-10</strong> — Informasjonskrav ved distribusjon: IPID, vederlagsinformasjon, rådgivningsdokument.</p>
              <p><strong className="text-foreground">Rundskriv 9/2019</strong> — Finanstilsynets forventninger til behovsanalyse: kartlegging av eksisterende dekning, risikoforhold, økonomi og behov.</p>
              <p><strong className="text-foreground">Vederlagsinformasjon</strong> — Kunden skal informeres om provisjonsgrunnlag og størrelse eller honorarsats før avtale inngås.</p>
            </div>
          </details>
        </>
      )}

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(o) => { if (!o) setDeleteId(null); }}
        title={T("Slette behovsanalyse?")}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
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
    <Suspense fallback={<div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>}>
      <IddContent />
    </Suspense>
  );
}
