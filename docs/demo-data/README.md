# Demo-data for anbud-flyten

Ferdige PDF-er du kan laste ned og bruke til å demonstrere hele
anbud-flyten end-to-end (risikoprofil ut → tilbud inn → AI-analyse).

14 risikoprofiler (3 fiktive + 11 reelle norske toppselskap) og 3
forsikringstilbud til å pare med.

## Last ned direkte fra GitHub

Høyreklikk → "Save link as" (eller klikk først, deretter Raw → høyreklikk):

### Risikoprofiler — fiktive SMBs

| Selskap | Bransje | Score | Last ned |
|---|---|---|---|
| Bergmann Industri AS | Metallproduksjon | 6 (moderat) | [risk_bergmann_industri.pdf](risk_bergmann_industri.pdf) |
| Nordlys Restaurantgruppe AS | Restaurant, 3 lokasjoner | 11 (høy) | [risk_nordlys_restaurant.pdf](risk_nordlys_restaurant.pdf) |
| Arcticom Consulting AS | Rådgivning | 3 (lav) | [risk_arcticom_consulting.pdf](risk_arcticom_consulting.pdf) |

### Risikoprofiler — norske toppselskap (fiktive tall, reelle navn)

| Selskap | Bransje | Score | Last ned |
|---|---|---|---|
| DNB Bank ASA | Bank | 4 (lav) | [risk_dnb.pdf](risk_dnb.pdf) |
| Telenor ASA | Telekom | 5 (lav/moderat) | [risk_telenor.pdf](risk_telenor.pdf) |
| NorgesGruppen ASA | Dagligvare | 5 (lav/moderat) | [risk_norgesgruppen.pdf](risk_norgesgruppen.pdf) |
| Kongsberg Gruppen ASA | Forsvar/luftfart | 7 (moderat) | [risk_kongsberg.pdf](risk_kongsberg.pdf) |
| Strawberry Hospitality AS | Hotel (Nordic) | 10 (moderat/høy) | [risk_strawberry.pdf](risk_strawberry.pdf) |
| SATS Group AS | Treningssenter | 8 (moderat) | [risk_sats.pdf](risk_sats.pdf) |
| Thon Hotels AS | Hotel Norge | 6 (moderat) | [risk_thon_hotels.pdf](risk_thon_hotels.pdf) |
| XXL ASA | Sportsbutikk | 13 (høy) | [risk_xxl.pdf](risk_xxl.pdf) |
| Norwegian Air Shuttle ASA | Flyselskap | 14 (høy) | [risk_norwegian_air.pdf](risk_norwegian_air.pdf) |
| Orkla ASA | Konsumprodukter | 4 (lav) | [risk_orkla.pdf](risk_orkla.pdf) |
| AS Vinmonopolet | Drikkevarer | 3 (lav) | [risk_vinmonopolet.pdf](risk_vinmonopolet.pdf) |

> **NB:** tallene i de norske profilene er omtrentlige og kun for demo-formål.
> Ingen av beløpene er verifisert mot faktiske årsregnskap.

### Forsikringstilbud (innkommende svar)

| Forsikringsselskap | Last ned |
|---|---|
| If Skadeforsikring | [tilbud_if_skadeforsikring.pdf](tilbud_if_skadeforsikring.pdf) |
| Gjensidige Forsikring | [tilbud_gjensidige.pdf](tilbud_gjensidige.pdf) |
| Tryg Forsikring | [tilbud_tryg.pdf](tilbud_tryg.pdf) |

## Slik bruker du dem i en full demo

1. Logg inn på [meglerai.no](https://meglerai.no) → opprett et nytt anbud
   for et av de tre selskapene ovenfor.
2. Last opp tilhørende `risk_*.pdf` som anbudspakke-vedlegg.
3. Legg til 3 insurer-mottakere (bruk Gmail-aliaser du kontrollerer,
   f.eks. `dittnavn+if@gmail.com`, `dittnavn+gjensidige@gmail.com`, ...).
4. Send invitasjonene fra appen. Subjectet vil inneholde
   `[ref: TENDER-X-Y]` – **ikke endre det**.
5. For hver mottaker: svar fra Gmail til `anbud@meglerai.no` med
   tilsvarende `tilbud_*.pdf` som vedlegg. Behold ref-tokenet i subject.
6. Innenfor ~30 sekunder:
   - 3 `TenderOffer`-rader opprettes i tender-detaljen
   - 3 in-app-notifikasjoner
   - "Sammenlign tilbud"-knappen aktiveres → AI genererer analyse

## Regenerere selv

Hvis du vil endre profilene eller selskapene:

```bash
uv run python scripts/generate_sample_risk_profiles.py
uv run python scripts/generate_sample_offers.py
```

Kildekode for profilene: `scripts/generate_sample_risk_profiles.py`
Kildekode for tilbudene: `scripts/generate_sample_offers.py`
