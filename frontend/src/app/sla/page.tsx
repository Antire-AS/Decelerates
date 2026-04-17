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
import { StepHeader, NavButtons } from "@/components/sla/SlaShared";
import { type SlaData } from "@/components/sla/slaConstants";
import { Step1ClientDetails } from "@/components/sla/Step1ClientDetails";
import { Step2Services } from "@/components/sla/Step2Services";
import { Step3Fees } from "@/components/sla/Step3Fees";
import { Step4TermsKyc } from "@/components/sla/Step4TermsKyc";

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

  const allLines = [...(data.insurance_lines ?? []), ...(data.other_lines ? [data.other_lines] : [])];

  const toggleLine = (line: string) => {
    const lines = new Set(data.insurance_lines ?? []);
    if (lines.has(line)) {
      lines.delete(line);
    } else {
      lines.add(line);
    }
    set({ insurance_lines: Array.from(lines) });
  };

  async function handleLookup() {
    if (!data.client_orgnr?.trim()) return;
    setLookupLoading(true);
    try {
      const prof = await getOrgProfile(data.client_orgnr);
      const org = prof.org as Record<string, unknown>;
      // org.adresse is an array of street lines from BRREG (api/services/brreg_client.py:75)
      const streetLines = Array.isArray(org.adresse)
        ? (org.adresse as string[]).filter(Boolean).join(" ")
        : String(org.adresse ?? "");
      set({
        client_navn: String(org.navn ?? ""),
        client_adresse: [streetLines, org.poststed].filter(Boolean).join(", "),
      });
    } catch { setErr("Oppslag feilet."); }
    finally { setLookupLoading(false); }
  }

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

  return (
    <div className="broker-card max-w-2xl">
      {step === 1 && (
        <Step1ClientDetails
          data={data} set={set} err={err} setErr={setErr}
          lookupLoading={lookupLoading} onLookup={handleLookup}
          onNext={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <Step2Services
          data={data} set={set} err={err} setErr={setErr}
          allLines={allLines} toggleLine={toggleLine}
          onBack={() => setStep(1)} onNext={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <Step3Fees
          data={data} set={set}
          allLines={allLines}
          onBack={() => setStep(2)} onNext={() => setStep(4)}
        />
      )}

      {step === 4 && (
        <Step4TermsKyc
          data={data} set={set} err={err} setErr={setErr}
          onBack={() => setStep(3)} onNext={() => setStep(5)}
        />
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
            <label className="label-xs" htmlFor="broker-firm-name">Firmanavn *</label>
            <input id="broker-firm-name" value={val("firm_name")} onChange={(e) => set("firm_name", e.target.value)} required className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="broker-orgnr">Org.nr</label>
            <input id="broker-orgnr" value={val("orgnr")} onChange={(e) => set("orgnr", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="broker-contact-name">Kontaktperson</label>
            <input id="broker-contact-name" value={val("contact_name")} onChange={(e) => set("contact_name", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="broker-contact-email">E-post</label>
            <input id="broker-contact-email" type="email" value={val("contact_email")} onChange={(e) => set("contact_email", e.target.value)} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="broker-contact-phone">Telefon</label>
            <input id="broker-contact-phone" value={val("contact_phone")} onChange={(e) => set("contact_phone", e.target.value)} className="input-sm w-full" />
          </div>
          <div className="col-span-2">
            <label className="label-xs" htmlFor="broker-address">Adresse</label>
            <textarea id="broker-address" value={val("address")} onChange={(e) => set("address", e.target.value)} rows={2}
              className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]" />
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
      {tab === "ny" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <NewAgreementWizard />
          <AgreementsList />
        </div>
      )}
      {tab === "mine" && <AgreementsList />}
      {tab === "innstillinger" && <BrokerSettingsForm />}
    </div>
  );
}
