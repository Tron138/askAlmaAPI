import asyncio
from playwright.async_api import async_playwright

USER_DATA_DIR = "./browser_session"

async def main():
    print("Starte Chat-Test...")
    
    async with async_playwright() as p:
        # Wir starten wieder mit der gespeicherten Session!
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False, # Wir lassen es noch sichtbar, damit wir zuschauen können
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0]
        
        print("\n--- Gehe zu Ask Alma ---")
        await page.goto("https://app.ask-alma.de/")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000) # Kurz warten, bis das UI komplett gerendert ist
        
        print("\n--- Suche Eingabefeld ---")
        # Bei fast allen KI-Chats ist das Eingabefeld ein <textarea>
        # Wir suchen das erste textarea auf der Seite
        eingabefeld = page.locator("textarea").first
        
        if await eingabefeld.count() > 0:
            print("Eingabefeld gefunden! Tippe Nachricht ein...")
            await eingabefeld.fill("Hallo Ask Alma, das ist ein automatisierter Test von Open Interpreter. Kannst du mich verstehen?")
            
            print("Drücke ENTER zum Senden...")
            await page.keyboard.press("Enter")
            
            # Du hast erwähnt, die URL ändert sich auf /chats/UUID. 
            # Wir warten 5 Sekunden, um zu sehen, ob das passiert.
            print("Warte 5 Sekunden auf Reaktion und URL-Änderung...")
            await page.wait_for_timeout(5000)
            
            print(f"Neue URL nach dem Senden: {page.url}")
            
        else:
            print("FEHLER: Konnte kein <textarea> finden. Die Seite nutzt wohl ein anderes HTML-Element für die Eingabe.")
            # Wir speichern den HTML-Code der Seite in eine Datei, damit du ihn mir schicken kannst
            html = await page.content()
            with open("alma_html_dump.txt", "w", encoding="utf-8") as f:
                f.write(html)
            print("Ich habe den HTML-Code in 'alma_html_dump.txt' gespeichert.")

        print("\nTest fertig. Schließe in 10 Sekunden...")
        await page.wait_for_timeout(10000)
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(main())