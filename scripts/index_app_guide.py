"""Indekser app-guide og begrepsforklaringer i kunnskapsbasen.

Kjøres én gang (idempotent — sletter og re-indekserer):
    uv run --env-file .env python scripts/index_app_guide.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

APP_GUIDE = """
# Broker Accelerator — Komplett funksjonsoversikt

## Dashboard (/dashboard)
Startside som viser meglerens nøkkeltall:
- Antall fornyelser neste 30 og 90 dager
- Totale premier i risiko neste 30 dager
- Åpne krav (claims)
- Aktiviteter som forfaller i dag
- Totalt antall aktive poliser og total premiebook
- Nylige aktiviteter på tvers av alle kunder

## Selskapsøk (/search)
Søk etter norske selskaper via BRREG (Brønnøysundregistrene).
- Søk på selskapsnavn eller organisasjonsnummer
- Vis fullstendig risikoprofil: risikoscore 0–20, egenkapitalandel, antall ansatte, industri
- Økonomi-fane: historiske regnskapstall, Altman Z''-score (konkursindikator), industribenchmark
- Kontakter: bestyrelse, nøkkelpersoner
- Forsikring-fane: aktive poliser, claims, behovsanalyse, tilbud
- CRM-fane: aktiviteter, notater, pipeline-status
- Chat-fane: AI-chat om selskapet basert på alle tilgjengelige data

## Pipeline (/pipeline)
Salgspipeline med Kanban-tavle. Stadier:
- Lead: Potensielle nye kunder
- Kvalifisert: Bekreftet interesse, behovsavklaring gjort
- Tilbudt: Tilbud sendt til kunden
- Bundet: Kunden har akseptert
- Vunnet: Signert og aktivert
- Tapt: Mistet til konkurrent eller kunden valgte bort

Hvert deal har: forventet premie, forventet sluttdato, eier, notater.

## Portefølje (/portfolio)
Administrer grupper av selskaper (porteføljer).
- Opprett navngitte porteføljer (f.eks. "SMB-kunder", "Eiendom")
- Legg til selskaper manuelt eller importer fra BRREG
- Risikoanalyse: Altman Z''-score per selskap (rød/gul/grønn)
- Premieanalyse: total premiebook, fordelt per produkt og fornyelsesmåned
- Konsentrasjonsanalyse: fordeling på industri, geografi, omsetningsstørrelse
- Varsler: selskaper med vesentlige finansielle endringer år over år

## Fornyelser (/renewals)
Oversikt over kommende polisefornyelser.
- Sortert på fornyelsesdato (nærmest først)
- Viser premie, forsikringsselskap, produkt, kunde
- Fremdriftsstadier: Ikke startet → Kontaktet → Tilbud innhentet → Fornyet / Ikke fornyet
- Kan filtreres på datoperiode

## Anbud (/tenders)
Multi-insurer RFQ-kampanjer (anbudsforespørsler).
- Opprett anbud for et selskap med produkttyper og frist
- Legg til forsikringsselskaper som mottakere (e-post med lenke til anbudsportal)
- Mottakerne laster opp sine tilbud via en sikker portal (/anbud/respond/[token])
- Sammenlign tilbud: AI analyserer alle innkomne tilbud og anbefaler beste valg
- Statuser: Utkast → Sendt → Lukket → Analysert
- AI-assistent: Chat om anbudsprosessen, status og strategi

## IDD / Behovsanalyse (/idd)
Insurance Distribution Directive — kartlegging av kundens forsikringsbehov.
- Registrer eksisterende forsikringer kunden har
- Angi risikotoleranse og spesielle krav
- Systemet anbefaler produkttyper basert på selskapets profil
- Genererer IDD-dokumentasjon som kan deles med kunden

## Forsikringsselskaper (/insurers)
Meglerens nettverk av forsikringsselskaper.
- Registrer kontaktpersoner og e-post per selskap
- Definer appetitt-matrise: hvilke produkttyper selskapet tilbyr
- Brukes som mottakerliste i anbudsprosesser
- Win/loss-statistikk per selskap

## Avtaler / SLA (/sla)
Rammeavtaler med kunder.
- Opprett SLA med forsikringslinjer, fee-struktur og varighet
- Generer PDF-avtale for signering
- Statuser: Utkast, Aktiv, Utløpt

## Kunnskapsbase (/knowledge)
Intern kunnskapsbase for meglerne.
- Last opp kursvideoer (transkriberes automatisk med AI)
- Last opp forsikringsdokumenter og policyer
- Semantisk søk på tvers av alt innhold
- RAG-chat: Still spørsmål basert på indeksert innhold
- Indekser lover og forskrifter (FAL, IDD-direktiv, etc.)

## Admin (/admin)
Administrasjon og konfigurasjon.
- Brukerhåndtering: inviter kolleger, sett roller
- Eksporter data (CSV)
- Demo-data: last ned eksempel-risikoprofiler og tilbud
- Revisjonslogg: full logg over alle handlinger i systemet
- Innkommende e-post: administrer anbud-svar som mottas på e-post

## Nøkkelbegreper

**Altman Z''-score**: Finansiell modell som predikerer konkursrisiko.
- Grønn (> 2.6): Lav risiko
- Gul (1.1–2.6): Gråsone
- Rød (< 1.1): Høy risiko / nær konkurs

**IDD**: Insurance Distribution Directive — EU-direktiv om forsikringsformidling.
Krever at megler dokumenterer kundens behov og at produktet passer kunden.

**RFQ**: Request for Quotation — anbudsforespørsel til forsikringsselskaper.

**Premiebok**: Total årlig premie fra alle aktive poliser megleren forvalter.

**Egenkapitalandel**: Egenkapital / Total eiendeler. Under 10% er risiko-signal.

**Pipeline-stadie**: Stadiet et salg befinner seg i (lead → vunnet/tapt).

**Appetite-matrise**: Oversikt over hvilke forsikringsprodukter et selskap tilbyr.

**Compliance**: Overholdelse av regelverk (IDD, GDPR, FAL).
GDPR-samtykke og revisjonslogg dokumenterer at megler handler i samsvar med loven.
"""

def main():
    import os
    from api.models._base import SessionLocal
    from api.container import configure, AppConfig
    from api.adapters.blob_storage_adapter import BlobStorageConfig
    from api.adapters.notification_adapter import NotificationConfig
    from api.adapters.serper_search_adapter import SerperSearchConfig
    from api.adapters.foundry_llm_adapter import FoundryConfig
    from api.adapters.msgraph_email_adapter import MsGraphConfig
    from api.adapters.secret_adapter import SecretConfig
    configure(AppConfig(
        blob=BlobStorageConfig(endpoint=os.getenv("AZURE_BLOB_ENDPOINT")),
        notification=NotificationConfig(conn_str=os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING"), sender=""),
        serper_search=SerperSearchConfig(api_key=os.getenv("SERPER_API_KEY")),
        foundry=FoundryConfig(base_url=os.getenv("AZURE_FOUNDRY_BASE_URL", ""), api_key=os.getenv("AZURE_FOUNDRY_API_KEY", "")),
        msgraph=MsGraphConfig(tenant_id=os.getenv("AZURE_AD_TENANT_ID", ""), client_id=os.getenv("AZURE_AD_CLIENT_ID", ""), client_secret=os.getenv("AZURE_AD_CLIENT_SECRET", "")),
        secret=SecretConfig(),
    ))
    from api.services import _chunk_and_store

    SOURCE_KEY = "app_guide"
    KNOWLEDGE_ORG = "knowledge"

    db = SessionLocal()
    try:
        from api.db import CompanyChunk
        deleted = db.query(CompanyChunk).filter(
            CompanyChunk.orgnr == KNOWLEDGE_ORG,
            CompanyChunk.source == SOURCE_KEY,
        ).delete()
        db.commit()
        if deleted:
            print(f"Slettet {deleted} gamle app-guide chunks.")

        chunks = _chunk_and_store(KNOWLEDGE_ORG, SOURCE_KEY, APP_GUIDE, db)
        print(f"Indeksert {chunks} nye app-guide chunks i kunnskapsbasen.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
