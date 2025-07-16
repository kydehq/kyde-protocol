# Dieses Modul ist der Experte für staatliche Förderungen. Es nutzt eine
# KI, um immer die aktuellsten Förderrichtlinien zu kennen.
# ---------------------------------------------------------------------------

# import openai
# from ..vector_db import vdb_client # Beispiel für eine Vektor-Datenbank

async def get_subsidies(product: dict, user_profile: dict) -> dict:
    """
    Findet die passenden staatlichen Förderungen für ein bestimmtes Produkt
    und ein Nutzerprofil.
    """
    print(f"INFO: Suche Förderungen für Produkt '{product.get('name')}'...")

    # --- Schritt 1: Relevanten Kontext aus der Vektor-Datenbank holen ---
    # Hier würdest du eine Suche in deiner Vektor-DB starten, die mit den
    # aktuellen PDF-Dokumenten von BAFA/KfW gefüttert wurde.
    # query = f"Förderung für Wärmepumpe {product.get('name')} für ein Einfamilienhaus in PLZ {user_profile.get('zip_code')} bei Tausch einer Ölheizung."
    # relevant_docs = await vdb_client.search(query)
    print("-> Schritt 1/3: Finde relevante Förder-Dokumente...")

    # --- Schritt 2: Präzise Anfrage an den LLM stellen ---
    # Der LLM bekommt die Frage und die relevanten Textstellen aus den PDFs als Kontext.
    # So kann er eine präzise, auf Fakten basierende Antwort geben.
    # prompt = f"Kontext: {relevant_docs}\n\nFrage: {query}\n\nAntworte mit dem exakten Förderbetrag in Euro und den wichtigsten Bedingungen."
    # llm_response = await openai.chat.completions.create(...)
    print("-> Schritt 2/3: Stelle präzise Anfrage an den LLM...")

    # --- Schritt 3: Antwort des LLM parsen und strukturieren ---
    # Die Text-Antwort der KI wird in ein sauberes Datenobjekt umgewandelt.
    # subsidy_details = parse_llm_response(llm_response)
    print("-> Schritt 3/3: Wandle KI-Antwort in strukturierte Daten um...")

    # Vorerst geben wir ein simuliertes Ergebnis zurück
    return {
        "amount_eur": 12750.0,
        "program_name": "BEG EM - Einzelmaßnahmen",
        "conditions": "Tausch einer fossilen Heizung, Einhaltung der Jahresarbeitszahl."
    }
