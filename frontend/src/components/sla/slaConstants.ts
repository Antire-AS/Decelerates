// Shared constants for SLA wizard components

export const INSURANCE_LINES: Record<string, string[]> = {
  "Skadeforsikringer": ["Ting / Avbrudd", "Bedrift-/Produktansvar", "Transport", "Motorvogn", "Prosjektforsikring"],
  "Financial Lines": ["Styreansvar (D&O)", "Kriminalitetsforsikring", "Profesjonsansvar", "Cyber", "Spesialforsikring"],
  "Personforsikringer": ["Yrkesskade", "Ulykke", "Gruppeliv", "Sykdom", "Reise", "Helseforsikring"],
  "Pensjonsforsikringer": ["Ytelsespensjon", "Innskuddspensjon", "Lederpensjon"],
  "Spesialdekning": ["Reassuranse", "Marine", "Energi", "Garanti"],
};

export const STANDARD_VILKAAR = `Avtalen gjelder for ett år med automatisk fornyelse, med mindre den sies opp skriftlig med fire måneders varsel.

All skriftlig kommunikasjon mellom partene skjer elektronisk, som utgangspunkt på norsk.

Kunden plikter å gi megler korrekt og fullstendig informasjon om forsikringsgjenstandene og risikoen, samt opplyse om tidligere forsikringsforhold og anmeldte skader.

Forsikringsselskapets premiefaktura sendes til Kunden for betaling direkte til forsikringsselskapet.

Meglers ansvar for rådgivningsfeil er begrenset til NOK 25 000 000 per oppdrag og NOK 50 000 000 per kalenderår.`;

export type SlaData = {
  client_orgnr?: string; client_navn?: string; client_adresse?: string; client_kontakt?: string;
  start_date?: string; account_manager?: string; insurance_lines?: string[]; other_lines?: string;
  fee_structure?: { lines: { line: string; type: string; rate?: number | null }[] };
  kyc_id_type?: string; kyc_id_ref?: string; kyc_signatory?: string; kyc_firmadato?: string;
};
