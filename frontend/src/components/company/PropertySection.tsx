"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Building, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  getOrgPropertyMetadata,
  patchOrgPropertyMetadata,
  type PropertyMetadataOut,
  type PropertyMetadataPatch,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * Manual-entry form for company property data — building year, fire
 * alarm, flammable materials, etc. Drives underwriting prep on the
 * Forsikring tab. Will be auto-populated by Kartverket Matrikkel /
 * Eiendomsverdi when those integrations land later (P3b).
 */

type Field = {
  key: keyof PropertyMetadataPatch;
  label: string;
  type: "text" | "number" | "checkbox" | "textarea";
  placeholder?: string;
};

const FIELDS: Field[] = [
  { key: "address", label: "Adresse", type: "text", placeholder: "Bergmannsveien 42, Oslo" },
  { key: "gnr_bnr", label: "Gnr/Bnr", type: "text", placeholder: "208/4517" },
  { key: "building_year", label: "Byggeår", type: "number", placeholder: "1985" },
  { key: "ground_area_m2", label: "Tomteareal (m²)", type: "number", placeholder: "1200" },
  { key: "primary_use", label: "Hovedbruk", type: "text", placeholder: "Kontorbygg / lager / produksjon" },
  { key: "construction", label: "Konstruksjon", type: "text", placeholder: "Betong + stål" },
  { key: "roof_type", label: "Taktype", type: "text", placeholder: "Papp / takstein / sedum" },
  { key: "fire_resistance_rating", label: "Brannmotstand", type: "text", placeholder: "REI 60" },
  { key: "fire_alarm", label: "Brannalarm", type: "text", placeholder: "Tilkoblet 110-sentral" },
  { key: "sprinkler", label: "Sprinkler", type: "checkbox" },
  { key: "flammable_materials", label: "Brennbare materialer", type: "textarea", placeholder: "Ammoniakk, lager 800 m²" },
  { key: "notes", label: "Notater", type: "textarea", placeholder: "Renovert 2019, ny ventilasjon" },
];

export function PropertySection({ orgnr }: { orgnr: string }) {
  const T = useT();
  const { data, mutate } = useSWR<PropertyMetadataOut>(
    `property-${orgnr}`,
    () => getOrgPropertyMetadata(orgnr),
  );

  // Local form state, seeded from server. Stays string-typed so the
  // input controls don't fight us on partial values like "198".
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!data?.metadata) return;
    const seeded: Record<string, string | boolean> = {};
    for (const f of FIELDS) {
      const v = data.metadata[f.key as string];
      if (v === undefined || v === null) continue;
      seeded[f.key] = f.type === "checkbox" ? Boolean(v) : String(v);
    }
    setDraft(seeded);
  }, [data]);

  function setField(key: string, value: string | boolean) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const patch: PropertyMetadataPatch = {};
      for (const f of FIELDS) {
        const raw = draft[f.key];
        if (raw === undefined || raw === "") continue;
        if (f.type === "number") {
          const n = Number(raw);
          if (!Number.isNaN(n)) (patch[f.key] as unknown as number) = n;
        } else if (f.type === "checkbox") {
          (patch[f.key] as unknown as boolean) = Boolean(raw);
        } else {
          (patch[f.key] as unknown as string) = String(raw);
        }
      }
      await patchOrgPropertyMetadata(orgnr, patch);
      await mutate();
      toast.success(T("Eiendomsdata lagret"));
    } catch {
      toast.error(T("Kunne ikke lagre"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="broker-card">
      <div className="flex items-center gap-2 mb-4">
        <Building className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">{T("Eiendomsdata")}</h3>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        {T(
          "Fyll inn det du vet — alle felt er valgfrie. Brukes som underlag i anbudspakken.",
        )}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {FIELDS.map((f) => (
          <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
            <label className="label-xs" htmlFor={`prop-${f.key}`}>
              {T(f.label)}
            </label>
            {f.type === "textarea" ? (
              <textarea
                id={`prop-${f.key}`}
                className="input-sm w-full min-h-[60px]"
                placeholder={f.placeholder ? T(f.placeholder) : undefined}
                value={String(draft[f.key] ?? "")}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            ) : f.type === "checkbox" ? (
              <label className="flex items-center gap-2 mt-1">
                <input
                  id={`prop-${f.key}`}
                  type="checkbox"
                  checked={Boolean(draft[f.key])}
                  onChange={(e) => setField(f.key, e.target.checked)}
                />
                <span className="text-xs text-muted-foreground">{T("Ja")}</span>
              </label>
            ) : (
              <input
                id={`prop-${f.key}`}
                type={f.type}
                className="input-sm w-full"
                placeholder={f.placeholder ? T(f.placeholder) : undefined}
                value={String(draft[f.key] ?? "")}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex justify-end mt-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {T("Lagre")}
        </button>
      </div>
    </div>
  );
}
