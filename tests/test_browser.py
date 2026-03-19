import asyncio
from playwright.async_api import async_playwright

USER_DATA_DIR = "./browser_session"

async def main():
    print("Starte Playwright Debugging-Sitzung...")
    
    async with async_playwright() as p:
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0]
        
        print("\n--- SCHRITT 1: Moodle Login ---")
        print("Gehe zu https://moodle.rwu.de...")
        await page.goto("https://moodle.rwu.de")
        
        print("PAUSE: Bitte logge dich jetzt im Browser manuell bei Moodle ein.")
        print("WICHTIG: Warte, bis dein Moodle-Dashboard komplett geladen ist!")
        print("Drücke danach ENTER hier in der Konsole.")
        
        # Asynchrones Warten auf User-Input, damit Playwright im Hintergrund nicht einfriert
        await asyncio.to_thread(input, "Warte auf ENTER... ")
        
        # Dem Browser 2 Sekunden Zeit geben, um eventuelle Redirects abzuschließen
        print("Lasse Browser kurz durchatmen...")
        await page.wait_for_timeout(2000)
        
        print("\n--- SCHRITT 2: Ask Alma aufrufen ---")
        print("Gehe zu https://app.ask-alma.de/#/ ...")
        # Wir zwingen Playwright, eventuell noch laufende Navigationen zu ignorieren/überschreiben
        await page.goto("https://app.ask-alma.de/")
        
        print("Warte, bis die Seite geladen ist...")
        # Warten, bis das Netzwerk ruhig ist (keine großen Ladevorgänge mehr)
        await page.wait_for_load_state("networkidle")
        
        aktuelle_url = page.url
        print(f"Aktuelle URL nach dem Laden: {aktuelle_url}")
        
        print("\n--- SCHRITT 3: DOM Analyse ---")
        html_content = await page.content()
        print(f"Länge des HTML-Dokuments: {len(html_content)} Zeichen")
        
        if "id=\"root\"" in html_content:
            print("ERFOLG: Das <div id=\"root\"> aus Ask Alma wurde gefunden! Die Seite ist da.")
        else:
            print("WARNUNG: Konnte das Root-Element nicht finden. Seite nicht richtig geladen?")
            
        print("\nTest abgeschlossen. Der Browser bleibt noch 60 Sekunden offen...")
        await page.wait_for_timeout(60000)
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(main())