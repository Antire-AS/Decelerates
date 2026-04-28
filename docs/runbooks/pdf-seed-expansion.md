# PDF_SEED_DATA expansion (Phase 4)

## What this runbook does

Takes `api/constants.py:PDF_SEED_DATA` from 4 demo companies (DNB, Gjensidige,
Søderberg, Equinor) to the top 17 Norwegian public companies brokers actually
look up. Closes the recall gap for the long-tail companies where BRREG
Regnskapsregisteret only returns the latest year and our agent pipeline
hits ~15% recall.

## Why this is manual

Each company's IR page has a different URL structure, naming convention,
and CDN. Scripting would mean re-inventing the agent pipeline we already
measured at 15%. Human hunt takes ~60-90 seconds per company.

## How to do it

### Step 1: Open each company's IR page

Right-click each link, Cmd+click to open in new tab:

- [Telenor ASA](https://www.telenor.com/about/investors/annual-reports/)
- [Schibsted ASA](https://schibsted.com/ir/)
- [Orkla ASA](https://www.orkla.com/investors/reports/)
- [Yara International ASA](https://www.yara.com/investor-relations/reports-presentations/)
- [Kongsberg Gruppen ASA](https://www.kongsberg.com/investors/reports-and-presentations/)
- [Storebrand ASA](https://www.storebrand.com/en/investor-relations/annual-reports)
- [Aker BP ASA](https://akerbp.com/en/financial-calendar/)
- [Tomra Systems ASA](https://www.tomra.com/en/investors/reports-and-presentations)
- [Grieg Seafood ASA](https://griegseafood.com/investor/reports-presentations/)
- [Veidekke ASA](https://veidekke.no/investor-relations/rapporter/)
- [Multiconsult ASA](https://www.multiconsult.no/om-oss/investorrelasjoner/)
- [NEL ASA](https://nelhydrogen.com/investor-relations/reports-presentations/)
- [NRC Group ASA](https://www.nrcgroup.com/en/investors/)
- [Kvaerner ASA](https://www.aker-solutions.com/investors/)
- [REC Silicon ASA](https://www.recsilicon.com/investors/)
- [Glommen Mjøsen Skog SA](https://www.glommen-mjosen.no/om-oss/arsrapporter/)
- [Borgestad ASA](https://www.borgestad.com/no/investor/finansielle-rapporter/)

### Step 2: For each page, find the **2024 Annual Report PDF link**

Look for: `Annual Report 2024` or `Årsrapport 2024` (never the summary, the
sustainability report, or the Q4 presentation — we want the full annual
report).

Right-click the link → **Copy Link Address**.

### Step 3: Paste into the template

Open `api/constants.py` and paste each entry into `PDF_SEED_DATA` under
its orgnr. The template below is ready to paste — just fill in the
`pdf_url` line for each company.

```python
PDF_SEED_DATA: Dict[str, List[Dict[str, Any]]] = {
    # ... existing DNB / Gjensidige / Søderberg / Equinor entries above ...

    "916862037": [  # Telenor ASA
        {
            "year": 2024,
            "pdf_url": "",  # PASTE URL HERE
            "label": "Telenor Annual Report 2024",
        },
    ],
    "933192410": [  # Schibsted ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Schibsted Annual Report 2024",
        },
    ],
    "930357618": [  # Orkla ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Orkla Annual Report 2024",
        },
    ],
    "999001369": [  # Yara International ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Yara Annual Report 2024",
        },
    ],
    "947990982": [  # Kongsberg Gruppen ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Kongsberg Gruppen Annual Report 2024",
        },
    ],
    "996525450": [  # Storebrand ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Storebrand Annual Report 2024",
        },
    ],
    "913540538": [  # Aker BP ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Aker BP Annual Report 2024",
        },
    ],
    "937681140": [  # Tomra Systems ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Tomra Systems Annual Report 2024",
        },
    ],
    "930860675": [  # Grieg Seafood ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Grieg Seafood Annual Report 2024",
        },
    ],
    "956936264": [  # Veidekke ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Veidekke Annual Report 2024",
        },
    ],
    "958935096": [  # Multiconsult ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Multiconsult Annual Report 2024",
        },
    ],
    "934382404": [  # NEL ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "NEL Annual Report 2024",
        },
    ],
    "981211524": [  # NRC Group ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "NRC Group Annual Report 2024",
        },
    ],
    "963936060": [  # Kvaerner ASA (now Aker Solutions)
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Kvaerner / Aker Solutions Annual Report 2024",
        },
    ],
    "970921093": [  # REC Silicon ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "REC Silicon Annual Report 2024",
        },
    ],
    "986470668": [  # Glommen Mjøsen Skog SA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Glommen Mjøsen Skog Annual Report 2024",
        },
    ],
    "975800761": [  # Borgestad ASA
        {
            "year": 2024,
            "pdf_url": "",
            "label": "Borgestad Annual Report 2024",
        },
    ],
}
```

### Step 4: Sanity-check before committing

The seed loader skips any entry with an empty `pdf_url`, so partial
completion is safe — you can land a first batch of 5 today and add
the rest later.

```bash
# Smoke test: verify each URL HEAD-OKs as a PDF
for url in $(grep 'pdf_url' api/constants.py | awk -F'"' '{print $4}' | grep "^http"); do
  status=$(curl -sL -o /dev/null -w "%{http_code} %{content_type}" "$url")
  echo "$status | $url"
done
```

Expect `200 application/pdf` for each. Anything else (404, text/html,
etc.) — open the URL in a browser and grab the direct PDF link.

### Step 5: Commit + PR

```bash
git add api/constants.py
git commit -m "feat(seed): expand PDF_SEED_DATA with top-17 Norwegian companies (Phase 4)"
gh pr create --base staging --title "feat(seed): PDF_SEED_DATA expansion (Phase 4)"
```

## Expected recall impact

Combined with Phase 2 (Bing) already merged:

- **Seeded companies** (4 existing + 17 new = 21): 100% recall, zero LLM cost
- **Unseeded companies**: ~10-13/20 via Bing
- **Overall projected**: 18-20/20 on the 20-company harness corpus

## If you want to expand beyond the top 17

The `TOP_100_NO_NAMES` list in `api/constants.py:124` has 100 broker-priority
companies. Add new entries to `PDF_SEED_DATA` as you encounter them in
real broker traffic. Annual refresh (January-April each year when companies
publish new reports) keeps the seed current.
