"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getSlaAgreements, createSlaAgreement, signSlaAgreement, downloadSlaPdf,
  getBrokerSettings, saveBrokerSettings,
  getOrgProfile,
  type SlaAgreement,
} from "@/lib/api";
import { Loader2, Download, CheckCircle2 } from "lucide-react";

// ── Constants ─────────────────────────────────────────────────────────────────

const INSURANCE_LINES: Record<string, string[]> = {
  "Skadeforsikringer": ["Ting / Avbrudd", "Bedrift-/Produktansvar", "Transport", "Motorvogn", "Prosjektforsikring"],
  "Financial Lines": ["Styreansvar (D&O)", "Kriminalitetsforsikring", "Profesjonsansvar", "Cyber", "Spesialforsikring"],
  "Personforsikringer": ["Yrkesskade", "Ulykke", "Gruppeliv", "Sykdom", "Reise", "Helseforsikring"],
  "Pensjonsforsikringer": ["Ytelsespensjon", "Innskuddspensjon", "Lederpensjon"],
  "Spesialdekning": ["Reassuranse", "Marine", "Energi", "Garanti"],
};

const STANDARD_VILKAAR = `Avtalen gjelder for ett år med automatisk fornyelse, med mindre den sies opp skriftlig med fire måneders varsel.

All skriftlig kommunikasjon mellom partene skjer elektronisk, som utgangspunkt på norsk.

Kunden plikter å gi megler korrekt og fullstendig informasjon om forsikringsgjenstandene og risikoen, samt opplyse om tidligere forsikringsforhold og anmeldte skader.

Forsikringsselskapets premiefaktura sendes til Kunden for betaling direkte til forsikringsselskapet.

Meglers ansvar for rådgivningsfeil er begrenset til NOK 25 000 000 per oppdrag og NOK 50 000 000 per kalenderår.`;

type SlaData = {
  client_orgnr?: string; client_navn?: string; client_adresse?: string; client_kontakt?: string;
  start_date?: string; account_manager?: string; insurance_lines?: string[]; other_lines?: string;
  fee_structure?: { lines: { line: string; type: string; rate?: number | null }[] };
  kyc_id_type?: string; kyc_id_ref?: string; kyc_signatory?: string; kyc_firmadato?: string;
};

// ── Step components ───────────────────────────────────────────────────────────

function StepHeader({ step, total, label }: { step: number; total: number; label: string }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-1.5 flex-1 bg-[#EDE8E3] rounded-full overflow-hidden">
          <div className="h-full bg-[#2C3E50] rounded-full transition-all" style={{ width: `${(step / total) * 100}%` }} />
        </div>
        <span className="text-xs text-[#8A7F74] whitespace-nowrap">Steg {step} av {total}</span>
      </div>
      <h2 className="text-sm font-semibold text-[#2C3E50]">{label}</h2>
    </div>
  );
}

function NavButtons({ onBack, onNext, nextLabel = "Neste →", nextDisabled = false, loading = false }: {
  onBack?: () => void; onNext: () => void; nextLabel?: string; nextDisabled?: boolean; loading?: boolean;
}) {
  return (
    <div className="flex gap-2 mt-4">
      {onBack && (
        <button onClick={onBack}
          className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3]">
          ← Tilbake
        </button>
      )}
      <button onClick={onNext} disabled={nextDisabled || loading}
        className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
        {loading && <Loader2 className="w-3 h-3 animate-spin" />}
        {nextLabel}
      </button>
    </div>
  );
}

// ── New Agreement Wizard ──────────────────────────────────────────────────────

function NewAgreementWizard() {
  const [step, setStep] = useState(1);
  const [data, setData] = useState<SlaData>({});
  const [err, setErr] = useState<string | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);

  const total = 5;
  const set = (patch: Partial<SlaData>) => setData((d) => ({ ...d, ...patch }));

  // Step 1: Client details
  async function handleLookup() {
    if (!data.client_orgnr?.trim()) return;
    setLookupLoading(true);
    try {
      const prof = await getOrgProfile(data.client_orgnr);
      const org = prof.org as Record<string, unknown>;
      set({
        client_navn: String(org.navn ?? ""),
        client_adresse: [org.adresse, org.poststed].filter(Boolean).join(", "),
      });
    } catch { setErr("Oppslag feilet."); }
    finally { setLookupLoading(false); }
  }

  // Step 2: insurance lines toggle
  const toggleLine = (line: string) => {
    const lines = new Set(data.insurance_lines ?? []);
    lines.has(line) ? lines.delete(line) : lines.add(line);
    set({ insurance_lines: Array.from(lines) });
  };

  // Step 5: generate
  async function handleGenerate() {
    setGenerating(true); setErr(null);
    try {
      const res = await createSlaAgreement({ form_data: data }) as { id: number };
      setCreatedId(res.id);
      await downloadSlaPdf(
        res.id,
        `tjenesteavtale_${data.client_orgnr ?? res.id}.pdf`,
      );
      setStep(1); setData({});
    } catch (e) { setErr(String(e)); }
    finally { setGenerating(false); }
  }

  const allLines = [...(data.insurance_lines ?? []), ...(data.other_lines ? [data.other_lines] : [])];

  return (
    <div className="broker-card max-w-2xl">
      {step === 1 && (
        <>
          <StepHeader step={1} total={total} label="Klientdetaljer" />
          <div className="space-y-3">
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="label-xs">Org.nr *</label>
                <input value={data.client_orgnr ?? ""} onChange={(e) => set({ client_orgnr: e.target.value })}
                  placeholder="9 siffer" className="input-sm w-full" />
              </div>
              <button onClick={handleLookup} disabled={lookupLoading}
                className="self-end px-3 py-1.5 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1">
                {lookupLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                Slå opp
              </button>
            </div>
            <div>
              <label className="label-xs">Klientnavn *</label>
              <input value={data.client_navn ?? ""} onChange={(e) => set({ client_navn: e.target.value })}
                className="input-sm w-full" />
            </div>
            <div>
              <label className="label-xs">Adresse</label>
              <textarea value={data.client_adresse ?? ""} onChange={(e) => set({ client_adresse: e.target.value })}
                rows={2} className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
            </div>
            <div>
              <label className="label-xs">Kontaktperson (navn + e-post)</label>
              <input value={data.client_kontakt ?? ""} onChange={(e) => set({ client_kontakt: e.target.value })}
                className="input-sm w-full" />
            </div>
          </div>
          {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
          <NavButtons onNext={() => { if (!data.client_navn?.trim()) { setErr("Klientnavn er påkrevd."); return; } setErr(null); setStep(2); }} />
        </>
      )}

      {step === 2 && (
        <>
          <StepHeader step={2} total={total} label="Tjenester (Vedlegg A)" />
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-xs">Avtalestartdato</label>
                <input type="date" value={data.start_date ?? new Date().toISOString().slice(0, 10)}
                  onChange={(e) => set({ start_date: e.target.value })} className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs">Kundeansvarlig</label>
                <input value={data.account_manager ?? ""} onChange={(e) => set({ account_manager: e.target.value })}
                  className="input-sm w-full" />
              </div>
            </div>
            <div>
              <p className="label-xs mb-2">Forsikringslinjer som megleres:</p>
              {Object.entries(INSURANCE_LINES).map(([cat, lines]) => (
                <div key={cat} className="mb-3">
                  <p className="text-xs font-medium text-[#8A7F74] mb-1">{cat}</p>
                  <div className="flex flex-wrap gap-2">
                    {lines.map((line) => (
                      <label key={line}
                        className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors ${
                          data.insurance_lines?.includes(line)
                            ? "bg-[#2C3E50] text-white border-[#2C3E50]"
                            : "border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3]"
                        }`}>
                        <input type="checkbox" className="hidden"
                          checked={!!data.insurance_lines?.includes(line)}
                          onChange={() => toggleLine(line)} />
                        {line}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              <div>
                <label className="label-xs">Andre (spesifiser)</label>
                <input value={data.other_lines ?? ""} onChange={(e) => set({ other_lines: e.target.value })}
                  className="input-sm w-full" />
              </div>
            </div>
          </div>
          <NavButtons
            onBack={() => setStep(1)}
            onNext={() => {
              if (!allLines.length) { setErr("Velg minst én forsikringslinje."); return; }
              setErr(null); setStep(3);
            }}
          />
          {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
        </>
      )}

      {step === 3 && (
        <>
          <StepHeader step={3} total={total} label="Honorar (Vedlegg B)" />
          <div className="space-y-4">
            {allLines.map((line) => {
              const existing = data.fee_structure?.lines.find((f) => f.line === line) ?? { line, type: "provisjon", rate: null };
              const update = (patch: Partial<typeof existing>) => {
                const lines = [...(data.fee_structure?.lines ?? [])];
                const idx = lines.findIndex((f) => f.line === line);
                const updated = { ...existing, ...patch };
                if (idx >= 0) lines[idx] = updated; else lines.push(updated);
                set({ fee_structure: { lines } });
              };
              return (
                <div key={line} className="p-3 bg-[#F9F7F4] rounded-lg">
                  <p className="text-xs font-semibold text-[#2C3E50] mb-2">{line}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="label-xs">Honorartype</label>
                      <select value={existing.type} onChange={(e) => update({ type: e.target.value, rate: null })}
                        className="input-sm w-full">
                        <option value="provisjon">Provisjon (%)</option>
                        <option value="fast">Fast honorar (NOK/år)</option>
                        <option value="ikke_avklart">Ikke avklart</option>
                      </select>
                    </div>
                    {existing.type !== "ikke_avklart" && (
                      <div>
                        <label className="label-xs">{existing.type === "provisjon" ? "Sats (%)" : "Beløp (NOK/år)"}</label>
                        <input type="number" min={0} value={existing.rate ?? ""}
                          onChange={(e) => update({ rate: e.target.value ? Number(e.target.value) : null })}
                          className="input-sm w-full" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <NavButtons onBack={() => setStep(2)} onNext={() => { setStep(4); }} />
        </>
      )}

      {step === 4 && (
        <>
          <StepHeader step={4} total={total} label="Vilkår og KYC" />
          <div className="space-y-4">
            <div className="bg-[#F9F7F4] rounded-lg p-3 max-h-48 overflow-y-auto">
              <p className="text-xs text-[#2C3E50] whitespace-pre-line">{STANDARD_VILKAAR}</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-xs">Type legitimasjon</label>
                <select value={data.kyc_id_type ?? "Pass"} onChange={(e) => set({ kyc_id_type: e.target.value })}
                  className="input-sm w-full">
                  {["Pass", "Nasjonalt ID-kort", "Bankkort med bilde", "Annet"].map((v) => <option key={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="label-xs">Dokumentreferanse / ID-nummer</label>
                <input value={data.kyc_id_ref ?? ""} onChange={(e) => set({ kyc_id_ref: e.target.value })}
                  placeholder="e.g. N12345678" className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs">Signatarens navn</label>
                <input value={data.kyc_signatory ?? ""} onChange={(e) => set({ kyc_signatory: e.target.value })}
                  className="input-sm w-full" />
              </div>
              <div>
                <label className="label-xs">Firmaattest dato</label>
                <input value={data.kyc_firmadato ?? ""} onChange={(e) => set({ kyc_firmadato: e.target.value })}
                  placeholder="DD.MM.ÅÅÅÅ" className="input-sm w-full" />
              </div>
            </div>
            {[
              "Kunden bekrefter å ha lest og forstått vilkårene.",
              "Kunden bekrefter at kundekontroll (KYC/AML) er gjennomført og legitimasjon er fremlagt.",
            ].map((label, i) => {
              const key = `kyc_accept_${i}` as keyof SlaData;
              return (
                <label key={i} className="flex items-start gap-2 text-xs text-[#2C3E50] cursor-pointer">
                  <input type="checkbox" className="mt-0.5 accent-[#4A6FA5]"
                    checked={!!(data as Record<string, unknown>)[key]}
                    onChange={(e) => set({ [key]: e.target.checked } as Partial<SlaData>)} />
                  {label}
                </label>
              );
            })}
          </div>
          <NavButtons
            onBack={() => setStep(3)}
            onNext={() => {
              const kyc = data.kyc_id_ref && data.kyc_signatory && data.kyc_firmadato;
              const accepted = (data as Record<string, unknown>).kyc_accept_0 && (data as Record<string, unknown>).kyc_accept_1;
              if (!kyc || !accepted) { setErr("Fyll ut alle KYC-felt og bekreft vilkårene."); return; }
              setErr(null); setStep(5);
            }}
          />
          {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
        </>
      )}

      {step === 5 && (
        <>
          <StepHeader step={5} total={total} label="Gjennomgang og generering" />
          <div className="space-y-3">
            <div className="bg-[#F9F7F4] rounded-lg p-4 space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><span className="text-xs text-[#8A7F74]">Klient</span><p className="font-medium">{data.client_navn}</p></div>
                <div><span className="text-xs text-[#8A7F74]">Org.nr</span><p className="font-medium">{data.client_orgnr ?? "—"}</p></div>
                <div><span className="text-xs text-[#8A7F74]">Startdato</span><p>{data.start_date}</p></div>
                <div><span className="text-xs text-[#8A7F74]">Kundeansvarlig</span><p>{data.account_manager ?? "—"}</p></div>
              </div>
              <div>
                <span className="text-xs text-[#8A7F74]">Forsikringslinjer</span>
                <p className="text-xs mt-0.5">{allLines.join(" · ") || "—"}</p>
              </div>
              {data.fee_structure?.lines && data.fee_structure.lines.length > 0 && (
                <div>
                  <span className="text-xs text-[#8A7F74]">Honorar</span>
                  <div className="mt-1 space-y-0.5">
                    {data.fee_structure.lines.map((f) => (
                      <p key={f.line} className="text-xs">
                        {f.line}: {f.type === "provisjon" ? `${f.rate ?? "—"}%` : f.type === "fast" ? `NOK ${f.rate?.toLocaleString("nb-NO") ?? "—"}/år` : "Ikke avklart"}
                      </p>
                    ))}
                  </div>
                </div>
              )}
              {data.kyc_signatory && (
                <div>
                  <span className="text-xs text-[#8A7F74]">KYC</span>
                  <p className="text-xs">{data.kyc_signatory} — {data.kyc_id_type} {data.kyc_id_ref}</p>
                </div>
              )}
            </div>
            {createdId && (
              <div className="flex items-center gap-2 text-xs text-green-700">
                <CheckCircle2 className="w-4 h-4" /> Avtale #{createdId} opprettet. PDF lastes ned automatisk.
              </div>
            )}
            {err && <p className="text-xs text-red-600">{err}</p>}
          </div>
          <NavButtons
            onBack={() => setStep(4)}
            onNext={handleGenerate}
            nextLabel="Opprett avtale og last ned PDF"
            loading={generating}
          />
        </>
      )}
    </div>
  );
}

// ── My Agreements ─────────────────────────────────────────────────────────────

function AgreementsList() {
  const { data: agreements, isLoading, mutate } = useSWR<SlaAgreement[]>("sla-agreements", getSlaAgreements);
  const [signingId, setSigningId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function handleSign(id: number) {
    setSigningId(id); setErr(null);
    try {
      await signSlaAgreement(id, "broker");
      mutate();
    } catch (e) { setErr(String(e)); }
    finally { setSigningId(null); }
  }

  async function handleDownload(sla: SlaAgreement) {
    setDownloadingId(sla.id); setErr(null);
    try {
      await downloadSlaPdf(sla.id, `tjenesteavtale_${sla.client_orgnr}.pdf`);
    } catch (e) { setErr(String(e)); }
    finally { setDownloadingId(null); }
  }

  if (isLoading) return <div className="broker-card"><Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" /></div>;
  if (!agreements?.length) return (
    <div className="broker-card text-center py-12">
      <p className="text-sm text-[#8A7F74]">Ingen avtaler ennå. Opprett en i «Ny avtale»-fanen.</p>
    </div>
  );

  return (
    <div className="broker-card">
      <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Mine avtaler ({agreements.length})</h2>
      {err && <p className="text-xs text-red-600 mb-2">{err}</p>}
      <div className="divide-y divide-[#EDE8E3]">
        {agreements.map((a) => {
          const aExt = a as SlaAgreement & { start_date?: string; status?: string; signed_at?: string };
          return (
            <div key={a.id} className="py-3 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[#2C3E50]">{a.client_name || a.client_orgnr}</p>
                <p className="text-xs text-[#8A7F74] mt-0.5">
                  {a.client_orgnr}
                  {aExt.start_date && ` · Start: ${aExt.start_date}`}
                  {` · Opprettet: ${new Date(a.created_at).toLocaleDateString("nb-NO")}`}
                </p>
                {aExt.signed_at && (
                  <p className="text-xs text-green-700 mt-0.5">
                    ✓ Signert {new Date(aExt.signed_at).toLocaleDateString("nb-NO")}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {!aExt.signed_at && (
                  <button onClick={() => handleSign(a.id)} disabled={signingId === a.id}
                    className="px-2.5 py-1 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50">
                    {signingId === a.id ? "…" : "Signer"}
                  </button>
                )}
                <button onClick={() => handleDownload(a)} disabled={downloadingId === a.id}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3] disabled:opacity-50">
                  {downloadingId === a.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  PDF
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Broker Settings ───────────────────────────────────────────────────────────

function BrokerSettingsForm() {
  const { data: saved, isLoading, mutate } = useSWR("broker-settings", getBrokerSettings);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const val = (key: string) => form[key] ?? saved?.[key] ?? "";
  const set = (key: string, v: string) => setForm((f) => ({ ...f, [key]: v }));

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!val("firm_name").trim()) { setMsg("Firmanavn er påkrevd."); return; }
    setSaving(true); setMsg(null);
    try {
      await saveBrokerSettings({
        firm_name: val("firm_name"),
        orgnr: val("orgnr"),
        address: val("address"),
        contact_name: val("contact_name"),
        contact_email: val("contact_email"),
        contact_phone: val("contact_phone"),
      });
      setMsg("Innstillinger lagret.");
      mutate();
    } catch (e) { setMsg(`Feil: ${String(e)}`); }
    finally { setSaving(false); }
  }

  if (isLoading) return <div className="broker-card"><Loader2 className="w-5 h-5 animate-spin text-[#4A6FA5]" /></div>;

  return (
    <div className="broker-card max-w-lg">
      <h2 className="text-sm font-semibold text-[#2C3E50] mb-1">Meglerinnstillinger</h2>
      <p className="text-xs text-[#8A7F74] mb-4">Disse opplysningene trykkes på alle avtaler du oppretter.</p>
      <form onSubmit={handleSave} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="label-xs">Firmanavn *</label>
            <input value={val("firm_name")} onChange={(e) => set("firm_name", e.target.value)} required className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs">Org.nr</label>
            <input value={val("orgnr")} onChange={(e) => set("orgnr", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs">Kontaktperson</label>
            <input value={val("contact_name")} onChange={(e) => set("contact_name", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs">E-post</label>
            <input type="email" value={val("contact_email")} onChange={(e) => set("contact_email", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs">Telefon</label>
            <input value={val("contact_phone")} onChange={(e) => set("contact_phone", e.target.value)} className="input-sm w-full" />
          </div>
          <div className="col-span-2">
            <label className="label-xs">Adresse</label>
            <textarea value={val("address")} onChange={(e) => set("address", e.target.value)} rows={2}
              className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
          </div>
        </div>
        {msg && <p className={`text-xs ${msg.startsWith("Feil") ? "text-red-600" : "text-green-700"}`}>{msg}</p>}
        <button type="submit" disabled={saving}
          className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50">
          {saving ? "Lagrer…" : "Lagre innstillinger"}
        </button>
      </form>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SlaPage() {
  const [tab, setTab] = useState<"ny" | "mine" | "innstillinger">("ny");

  const TAB = (t: typeof tab, label: string) => (
    <button key={t} onClick={() => setTab(t)}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        tab === t ? "bg-[#2C3E50] text-white" : "text-[#8A7F74] hover:bg-[#EDE8E3]"
      }`}>
      {label}
    </button>
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Avtaler</h1>
        <p className="text-sm text-[#8A7F74] mt-1">SLA-avtaler og meglermandat med kunder</p>
      </div>
      <div className="flex gap-2">
        {TAB("ny", "Ny avtale")}
        {TAB("mine", "Mine avtaler")}
        {TAB("innstillinger", "Meglerinnstillinger")}
      </div>
      {tab === "ny" && <NewAgreementWizard />}
      {tab === "mine" && <AgreementsList />}
      {tab === "innstillinger" && <BrokerSettingsForm />}
    </div>
  );
}
