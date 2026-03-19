import asyncio
import time
from playwright.async_api import async_playwright

USER_DATA_DIR = "./browser_session"

async def main():
    print("Starte optimierten Chat-Lese-Test...")
    
    async with async_playwright() as p:
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0]
        
        print("\n--- Gehe zu Ask Alma ---")
        await page.goto("https://app.ask-alma.de/")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        
        eingabefeld = page.locator("textarea").first
        
        # 1. Zähle die Antworten VOR dem Senden
        # Laut deinem HTML-Dump hat jede KI-Antwort die Klasse "markdown-body"
        antwort_locator = page.locator(".markdown-body")
        anzahl_vorher = await antwort_locator.count()
        print(f"[Info] Anzahl der bisherigen KI-Antworten im Chat: {anzahl_vorher}")
        
        # Wir fragen nach etwas, das ein bisschen länger dauert (Code + Erklärung)
        test_frage = "Schreibe mir ein kurzes Python-Skript, das bis 10 zählt, und erkläre lange, wie es funktioniert."
        print(f"\nSende Frage: '{test_frage}'")
        await eingabefeld.fill(test_frage)
        await page.keyboard.press("Enter")
        
        print("\n--- Warte dynamisch auf die Antwort ---")
        
        # 2. Warte, bis die KI ANFÄNGT zu antworten (eine neue Box erscheint)
        neue_antwort_index = anzahl_vorher
        start_wait = time.time()
        
        print("[Info] Warte darauf, dass die KI reagiert...")
        while await antwort_locator.count() <= anzahl_vorher:
            if time.time() - start_wait > 30: # Not-Aus nach 30 Sekunden ohne jede Reaktion
                print("FEHLER: KI hat nach 30 Sekunden nicht mal angefangen zu antworten!")
                await browser_context.close()
                return
            await asyncio.sleep(0.5)
            
        print("[Info] Neue Antwort-Box erkannt! Überwache den Stream-Prozess...")
        
        # 3. Überwache den Text der NEUEN Antwortbox
        das_neue_element = antwort_locator.nth(neue_antwort_index)
        
        letzter_text = ""
        gleicher_text_zaehler = 0
        check_interval = 0.5  # Alle halbe Sekunde prüfen
        max_idle_checks = 4   # Wenn der Text 4x gleich ist (also 2 Sekunden lang), sind wir fertig
        max_total_wait = 180  # Absolute Notbremse: Maximal 3 Minuten warten
        
        start_stream = time.time()
        
        while time.time() - start_stream < max_total_wait:
            # Wir holen uns den aktuell sichtbaren Text der Antwortbox
            aktueller_text = await das_neue_element.inner_text()
            
            if aktueller_text == letzter_text and aktueller_text.strip() != "":
                # Der Text hat sich nicht verändert
                gleicher_text_zaehler += 1
                print(f"  ... Text unverändert (Check {gleicher_text_zaehler}/{max_idle_checks})")
                
                if gleicher_text_zaehler >= max_idle_checks:
                    print("\nERFOLG: Die KI ist fertig mit Tippen!")
                    break
            else:
                # Text wächst weiter! Zähler wieder auf 0 setzen.
                if aktueller_text != letzter_text:
                    print(f"  ... KI tippt weiter (Aktuelle Länge: {len(aktueller_text)} Zeichen)")
                gleicher_text_zaehler = 0
                letzter_text = aktueller_text
                
            await asyncio.sleep(check_interval)

        print("\n--- EXTRAHIERTE ANTWORT ---")
        print("-" * 50)
        print(letzter_text)
        print("-" * 50)
            
        print("\nSchließe Browser in 5 Sekunden...")
        await page.wait_for_timeout(5000)
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(main())