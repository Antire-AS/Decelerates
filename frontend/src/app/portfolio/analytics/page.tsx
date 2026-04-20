"use client";

import { useState } from "react";
import Link from "next/link";
import PremiumTab    from "./_tabs/PremiumTab";
import ProvisjonTab  from "./_tabs/ProvisjonTab";
import PortfolioTab  from "./_tabs/PortfolioTab";
import CompareTab    from "./_tabs/CompareTab";
import NlQueryTab    from "./_tabs/NlQueryTab";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

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
          <h1 className="text-2xl font-bold text-foreground">Porteføljeanalyse</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Premievolum, provisjonsanalyse, portefølje og sammenligning av selskaper
          </p>
        </div>
        <Link href="/portfolio" className="text-xs text-primary hover:underline">← Tilbake til portefølje</Link>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabId)}>
        <TabsList className="flex-wrap justify-start bg-transparent p-0 h-auto gap-2">
          {TABS.map((t) => (
            <TabsTrigger
              key={t.id}
              value={t.id}
              className="data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-none bg-muted text-muted-foreground hover:bg-muted px-4 py-2 text-sm font-medium rounded-lg"
            >
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="premium"   className="focus-visible:ring-0"><PremiumTab /></TabsContent>
        <TabsContent value="provisjon" className="focus-visible:ring-0"><ProvisjonTab /></TabsContent>
        <TabsContent value="portfolio" className="focus-visible:ring-0"><PortfolioTab /></TabsContent>
        <TabsContent value="compare"   className="focus-visible:ring-0"><CompareTab /></TabsContent>
        <TabsContent value="nlquery"   className="focus-visible:ring-0"><NlQueryTab /></TabsContent>
      </Tabs>
    </div>
  );
}
