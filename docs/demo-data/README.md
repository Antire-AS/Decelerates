# Demo-data for anbud-flyten

Seks ferdige PDF-er du kan laste ned og bruke til å demonstrere hele
anbud-flyten end-to-end (risikoprofil ut → tilbud inn → AI-analyse).

## Last ned direkte fra GitHub

Høyreklikk → "Save link as" (eller klikk først, deretter Raw → høyreklikk):

### Risikoprofiler (utgående anbudspakker)

| Selskap | Risikoscore | Last ned |
|---|---|---|
| Bergmann Industri AS | 6 (moderat) | [risk_bergmann_industri.pdf](risk_bergmann_industri.pdf) |
| Nordlys Restaurantgruppe AS | 11 (høy) | [risk_nordlys_restaurant.pdf](risk_nordlys_restaurant.pdf) |
| Arcticom Consulting AS | 3 (lav) | [risk_arcticom_consulting.pdf](risk_arcticom_consulting.pdf) |

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
