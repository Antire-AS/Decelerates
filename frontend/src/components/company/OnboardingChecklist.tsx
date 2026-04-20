"use client";

import useSWR from "swr";
import { Check, Circle } from "lucide-react";
import {
  getOrgContacts,
  getOrgActivities,
  getOrgPolicies,
  getOrgClaims,
  getOrgRecommendations,
} from "@/lib/api";

/**
 * Plan §🟢 #21 — onboarding checklist for a single client.
 *
 * Pure derivation: counts existing rows (contacts, activities, policies,
 * claims, recommendations) and renders ✅/⬜ accordingly. No new backend
 * endpoint, no migration. The user clicks an item and gets routed to the
 * relevant CRM tab to act on it.
 */
type ChecklistItem = {
  label: string;
  done: boolean;
  hint: string;
  tabHash?: string;  // anchor on the company profile page
};

export function OnboardingChecklist({ orgnr }: { orgnr: string }) {
  // Reuse the same SWR cache keys the rest of the company profile uses so
  // we don't double-fetch when both are mounted.
  const { data: contacts = [] } = useSWR(`contacts-${orgnr}`, () => getOrgContacts(orgnr));
  const { data: activities = [] } = useSWR(`activities-${orgnr}`, () => getOrgActivities(orgnr));
  const { data: policies = [] } = useSWR(`policies-${orgnr}`, () => getOrgPolicies(orgnr));
  const { data: claims = [] } = useSWR(`claims-${orgnr}`, () => getOrgClaims(orgnr));
  const { data: recommendations = [] } = useSWR(
    `recommendations-${orgnr}`,
    () => getOrgRecommendations(orgnr),
  );

  const items: ChecklistItem[] = [
    {
      label: "Selskap lagt til",
      // The presence of any data implies the company is in our DB.
      done: true,
      hint: "Selskapet er registrert i databasen",
    },
    {
      label: "Kontaktperson registrert",
      done: contacts.length > 0,
      hint: "Legg til minst én kontaktperson under CRM-fanen",
      tabHash: "#crm",
    },
    {
      label: "Første aktivitet logget",
      done: activities.length > 0,
      hint: "Logg en samtale, e-post eller møte under CRM-fanen",
      tabHash: "#crm",
    },
    {
      label: "Forsikringspolise registrert",
      done: policies.length > 0,
      hint: "Legg til en aktiv polise for å spore portefølje og fornyelser",
      tabHash: "#crm",
    },
    {
      label: "Skader vurdert",
      done: claims.length > 0,
      hint: "Registrer evt. åpne skader for full compliance-trail",
      tabHash: "#crm",
    },
    {
      label: "Anbefalingsbrev sendt",
      done: recommendations.length > 0,
      hint: "Generer en formell anbefaling under CRM-fanen",
      tabHash: "#crm",
    },
  ];

  const completedCount = items.filter((i) => i.done).length;
  const progress = Math.round((completedCount / items.length) * 100);

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-foreground">Onboarding-sjekkliste</p>
        <span className="text-xs text-muted-foreground">
          {completedCount} / {items.length} fullført
        </span>
      </div>
      {/* Progress bar */}
      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-primary transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.label} className="flex items-start gap-2">
            {item.done ? (
              <Check className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            ) : (
              <Circle className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
            )}
            <div className="min-w-0 flex-1">
              <p className={`text-xs ${item.done ? "text-muted-foreground line-through" : "text-foreground font-medium"}`}>
                {item.label}
              </p>
              {!item.done && (
                <p className="text-[10px] text-muted-foreground mt-0.5">{item.hint}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
