"use client";

import { useState } from "react";
import Link from "next/link";
import PremiumTab    from "./_tabs/PremiumTab";
import ProvisjonTab  from "./_tabs/ProvisjonTab";
import PortfolioTab  from "./_tabs/PortfolioTab";
import CompareTab    from "./_tabs/CompareTab";
import NlQueryTab    from "./_tabs/NlQueryTab";

const TABS = [
  { id: "premium",    label: "Premieanalyse" },
  { id: "provisjon",  label: "Provisjon" },
  { id: "portfolio",  label: "Portefølje" },
  { id: "compare",    label: "Sammenlign selskaper" },
  { id: "nlquery",    label: "AI-spørring" },
] as const;

type TabId = typeof TABS[number]["id"];

export default function PortfolioAnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("premium");

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Porteføljeanalyse</h1>
          <p className="text-sm text-[#8A7F74] mt-1">
            Premievolum, provisjonsanalyse, portefølje og sammenligning av selskaper
          </p>
        </div>
        <Link href="/portfolio" className="text-xs text-[#4A6FA5] hover:underline">← Tilbake til portefølje</Link>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === t.id ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
            }`}>{t.label}</button>
        ))}
      </div>

      {activeTab === "premium"   && <PremiumTab />}
      {activeTab === "provisjon" && <ProvisjonTab />}
      {activeTab === "portfolio" && <PortfolioTab />}
      {activeTab === "compare"   && <CompareTab />}
      {activeTab === "nlquery"   && <NlQueryTab />}
    </div>
  );
}
