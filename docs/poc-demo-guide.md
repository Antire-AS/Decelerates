# Broker Accelerator — POC Demo Guide

> Bruk denne guiden når du presenterer meglerai.no for en megler.
> Hver seksjon matcher en side i sidebaren.

---

## 1. Hjem (Dashboard)
**URL:** `meglerai.no/dashboard`

**Hva du viser:**
- Oversikt over hele porteføljen på ett sted
- KPI-er: fornyelser neste 30 dager, aktive avtaler, åpne skader, forfalt aktiviteter
- Samlet premievolum med varsler
- Siste aktiviteter (samtaler, e-poster, møter)
- Hurtignavigasjon til de viktigste funksjonene

**Salgspoeng:** "Alt du trenger å se når du starter arbeidsdagen — på ett sted."

---

## 2. Selskapsøk
**URL:** `meglerai.no/search`

**Hva du viser:**
- Søk på firmanavn eller organisasjonsnummer
- Data hentes automatisk fra BRREG
- Risikoscore beregnes umiddelbart
- Klikk på et selskap for å åpne full profil

**Salgspoeng:** "Skriv inn et navn — vi henter alt fra offentlige registre automatisk."

---

## 3. Selskapsprofil (6 faner)
**URL:** `meglerai.no/search/984851006` (eksempel: DNB)

### 3a. Oversikt
- Selskapsdata: org.nr, adresse, bransje, stiftelsesdato
- Nøkkeltall: omsetning, resultat, egenkapitalandel
- **Risikoscore 0–20** med forklaring per faktor (selskapsstatus, økonomi, bransje, eksponering)
- Risikoveiledning ("Normalpremie forventes" → "Tegning kan være vanskelig")
- Styremedlemmer og roller
- Bransjesammenligning (benchmark mot SSB-data)
- Kart over selskapets lokasjon
- Lisenser fra Finanstilsynet

**Salgspoeng:** "Full due diligence på 2 sekunder — risikoscore, styret, økonomi, alt."

### 3b. Økonomi
- Historiske regnskapstall (fra BRREG + PDF-utvinning av årsrapporter)
- Grafer: omsetning, resultat, egenkapital over tid
- Last opp årsrapport-PDF → AI trekker ut tallene automatisk
- AI-generert finanskommentar

**Salgspoeng:** "Last opp en PDF, og AI-en leser hele årsrapporten for deg."

### 3c. Forsikring / CRM
Komplett kundebehandlingssystem:

| Seksjon | Hva |
|---------|-----|
| **Kontaktpersoner** | Navn, tittel, e-post, telefon. Marker primærkontakt. |
| **Forsikringer** | Aktive poliser med forsikringsgiver, premie, dekning, fornyelsesdato, provisjon |
| **Tilbudsinnhenting** | Innsendte forespørsler til forsikringsselskaper med status |
| **Anbefalinger** | AI-genererte produktanbefalinger basert på selskapets profil |
| **Skader** | Registrerte skader med beløp, status, forsikringsgiver |
| **Aktiviteter** | Logg over samtaler, e-poster, møter, oppgaver med forfallsdato |
| **Klientportal** | Generer en delbar lenke kunden kan åpne (skrivebeskyttet) |

**Salgspoeng:** "Alt om kunden — poliser, skader, kontakter, aktiviteter — i én fane."

### 3d. Notater
- Fritekst notater per selskap

### 3e. Chat
- Still spørsmål om selskapet til AI-assistenten
- Kontekstbevisst — kjenner selskapets økonomi, risikoprofil og poliser

**Salgspoeng:** "Spør AI-en: 'Hva bør jeg tenke på ved fornyelse av DNB?' — den kjenner all dataen."

---

## 4. Pipeline
**URL:** `meglerai.no/pipeline`

**Hva du viser:**
- Kanban-tavle med dra-og-slipp
- Steg: Henvendelse → Tilbud sendt → Forhandling → Vunnet / Tapt
- Opprett nye saker, flytt mellom kolonner

**Salgspoeng:** "Se alle dine pågående saker som et kanban-board — dra kortet når status endrer seg."

---

## 5. Portefølje
**URL:** `meglerai.no/portfolio`

**Hva du viser:**
- Opprett navngitte porteføljer (f.eks. "Eiendom Oslo", "Industri Vestland")
- Risikofordeling (kakediagram), bransjefordeling (stolpediagram)
- Filtrer selskaper etter risikobånd (Lav / Moderat / Høy / Svært høy)
- Klikk "Analyse" for dypere analyse

**Salgspoeng:** "Grupper kundene dine, se risikokonsentrasjon, og finn hull i porteføljen."

### Porteføljedetalj (`/portfolio/[id]`)
- Konsentrasjonsanalyse (hvem har størst premie)
- Risikovarsel (selskaper med finansielle advarsler)
- Kart over alle selskaper i porteføljen
- Last ned porteføljerapport som PDF
- AI-chat: "Hvilke selskaper har størst risiko for konkurs?"

### Porteføljeanalyse (`/portfolio/analytics`)
5 faner:
- **Premie** — volum per forsikringsgiver og produkttype
- **Provisjon** — provisjonsfordeling per selskap
- **Portefølje** — vekst og sammensetning
- **Sammenlign** — side-by-side sammenligning av selskaper
- **AI-spørring** — still spørsmål med naturlig språk ("Hvem har høyest omsetning?")

---

## 6. Prospektering
**URL:** `meglerai.no/prospecting`

**Hva du viser:**
- Avansert filtrering: bransje, kommune, omsetning, risikoscore
- Finn selskaper som matcher din ideelle kundeprofil
- Legg direkte til i en portefølje med ett klikk

**Salgspoeng:** "Finn nye kunder som passer din nisje — filtrer på bransje, størrelse og risiko."

---

## 7. Fornyelser
**URL:** `meglerai.no/renewals`

**Hva du viser:**
- Tidslinje: 30, 60, 90, 180 dager frem
- Status per fornyelse: Ikke startet → Klar for tilbud → Tilbud sendt → Akseptert/Avslått
- Bytt mellom tabell- og kanban-visning
- AI-generert fornyelsesbriefing per kunde
- Ferdig utkast til e-post til kunden
- Eksporter til Excel

**Salgspoeng:** "Aldri glem en fornyelse igjen. AI skriver briefing og e-postutkast for deg."

---

## 8. IDD / Behov
**URL:** `meglerai.no/idd`

**Hva du viser:**
- Behovsanalyse etter forsikringsformidlingsloven §§ 5-4, 7-1 til 7-10
- Risikoappetitt (lav/middels/høy)
- Risikofaktorer (eiendom, ansatte, kjøretøy, profesjonsansvar, cyber)
- Anbefalte produkter med begrunnelse (IDD § 7-7)
- Honorargrunnlag (provisjon, honorar, eller begge)
- Historikk over alle behovsanalyser

**Salgspoeng:** "IDD-compliance bygget inn. Behovsanalysen er ferdig utfylt med data vi allerede har."

---

## 9. Forsikringsselskaper
**URL:** `meglerai.no/insurers`

**Hva du viser:**
- Katalog over forsikringsselskaper du jobber med
- Kontaktperson, e-post, telefon
- Produktappetitt (hvilke produkttyper de tegner)
- Søk og filtrer

**Salgspoeng:** "Oversikt over alle selskaper du plasserer forsikring hos — hvem dekker hva."

---

## 10. Avtaler (SLA)
**URL:** `meglerai.no/sla`

**Hva du viser:**
- 5-stegs veiviser for å opprette megleravtale:
  1. Klientinfo (org.nr → autofyll fra BRREG)
  2. Tjenester (velg forsikringslinjer)
  3. Honorar (provisjon % eller fast honorar per linje)
  4. Vilkår & KYC (signer-info, ID-type)
  5. Gjennomgang → Generer PDF
- Liste over alle avtaler med signeringsstatus
- Last ned som PDF
- Signer avtale (Signicat e-signering)

**Salgspoeng:** "Fra org.nummer til ferdig megleravtale med e-signering på 3 minutter."

---

## 11. Kunnskapsbase
**URL:** `meglerai.no/knowledge`

6 faner:

| Fane | Hva |
|------|-----|
| **Chat** | AI-assistent som svarer på forsikringsspørsmål med kilder |
| **Søk** | Semantisk søk i alle opplastede dokumenter |
| **Analyse** | Trendanalyse og mest refererte emner |
| **Dokumenter** | Last opp og bla i forsikringsdokumenter, maler, guider |
| **Videoer** | Opplæringsvideoer og produktdemoer |
| **Administrer** | Indekser og vedlikehold kunnskapsbasen |

**Salgspoeng:** "AI-en har lest alle dokumentene dine. Spør hva som helst."

---

## 12. Admin
**URL:** `meglerai.no/admin`

**Hva du viser (for demo):**
- Systemstatistikk: antall selskaper, poliser, dokumenter, avtaler
- **Seed demo-data** — fyll inn realistisk testdata med ett klikk
- Brukerstyring
- Revisjonslogg (hvem gjorde hva, når)
- Eksport av data (CSV)
- E-postvarsler: porteføljedigest, aktivitetspåminnelser, fornyelsesvarsel

---

## 13. Klientportal (for kunden)
**URL:** `meglerai.no/portal/[token]`

**Hva du viser:**
- Skrivebeskyttet portal kunden ser
- Selskapsinformasjon, risikoscore
- Aktive poliser med detaljer
- Skadehistorikk
- Delte dokumenter
- Ingen innlogging — token-basert tilgang

**Salgspoeng:** "Del en lenke med kunden. De ser polisene sine, skadene, og dokumenter — uten innlogging."

---

## Demo-rekkefølge (anbefalt)

1. **Dashboard** — "Her starter dagen din"
2. **Selskapsøk** → søk "DNB" → åpne profil
3. **Selskapsprofil** — vis Oversikt (risikoscore), Økonomi (grafer), CRM (poliser)
4. **Portefølje** — vis risikofordeling og kart
5. **Pipeline** — dra et kort fra "Henvendelse" til "Tilbud sendt"
6. **Fornyelser** — vis AI-briefing og e-postutkast
7. **IDD** — vis ferdig behovsanalyse
8. **Avtaler** — lag en avtale fra scratch (5 steg)
9. **Klientportal** — vis hva kunden ser
10. **Kunnskapsbase** — still AI-en et spørsmål

**Tidsbruk:** ~15–20 minutter for full gjennomgang

---

## Nøkkelbudskap

> **For megleren:** "Du bruker i dag 2 timer på due diligence per kunde. Med Broker Accelerator tar det 2 minutter."

> **For ledelsen:** "Full oversikt over porteføljerisiko, fornyelser og compliance — i sanntid."

> **For compliance:** "IDD-behovsanalyser, revisjonslogg og KYC bygget inn fra dag 1."
