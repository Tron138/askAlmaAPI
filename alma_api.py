import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from playwright.async_api import async_playwright

USER_DATA_DIR = "./browser_session"

class AlmaBrowser:
    def __init__(self):
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.is_ready = False

    async def start(self):
        """Startet den Browser und navigiert zur Chat-Seite."""
        print("[Browser] Starte Playwright...")
        self.playwright = await async_playwright().start()
        
        # Du kannst headless auf True setzen, wenn du das Fenster später nicht mehr sehen willst!
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False, 
            viewport={"width": 1280, "height": 800}
        )
        self.page = self.browser_context.pages[0]
        
        print("[Browser] Gehe zu Ask Alma...")
        await self.page.goto("https://app.ask-alma.de/")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)
        self.is_ready = True
        print("[Browser] Bereit für Eingaben von Open Interpreter!")

    async def send_message(self, text: str) -> str:
        """Sendet eine Nachricht und wartet dynamisch auf die gestreamte Antwort."""
        if not self.is_ready:
            return "Fehler: Browser ist noch nicht bereit."

        try:
            print(f"[Browser] Sende Nachricht ({len(text)} Zeichen)...")
            
            eingabefeld = self.page.locator("textarea").first
            antwort_locator = self.page.locator(".markdown-body")
            
            # 1. Zähle vorherige Antworten
            anzahl_vorher = await antwort_locator.count()
            
            # 2. Text eintragen und senden
            await eingabefeld.fill(text)
            await self.page.keyboard.press("Enter")
            
            # 3. Warten, bis KI anfängt zu tippen
            neue_antwort_index = anzahl_vorher
            start_wait = time.time()
            
            while await antwort_locator.count() <= anzahl_vorher:
                if time.time() - start_wait > 30:
                    return "Fehler: KI hat nach 30 Sekunden nicht geantwortet."
                await asyncio.sleep(0.5)
                
            # 4. Stream überwachen (Polling)
            das_neue_element = antwort_locator.nth(neue_antwort_index)
            letzter_text = ""
            gleicher_text_zaehler = 0
            
            start_stream = time.time()
            max_total_wait = 180 # Max 3 Minuten
            
            while time.time() - start_stream < max_total_wait:
                aktueller_text = await das_neue_element.inner_text()
                
                if aktueller_text == letzter_text and aktueller_text.strip() != "":
                    gleicher_text_zaehler += 1
                    # Wenn Text 4x gleich bleibt (ca. 2 Sekunden), ist die KI fertig
                    if gleicher_text_zaehler >= 4:
                        break
                else:
                    gleicher_text_zaehler = 0
                    letzter_text = aktueller_text
                    
                await asyncio.sleep(0.5)
            
            print("[Browser] Antwort erfolgreich extrahiert.")
            return letzter_text
            
        except Exception as e:
            return f"Fehler bei der Browser-Interaktion: {str(e)}"

    async def stop(self):
        if self.browser_context:
            await self.browser_context.close()
        if self.playwright:
            await self.playwright.stop()

# Globale Instanzen
alma_browser = AlmaBrowser()
app = FastAPI(title="Ask Alma API Bridge")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(alma_browser.start())

@app.on_event("shutdown")
async def shutdown_event():
    await alma_browser.stop()

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Der Drop-In-Ersatz für OpenAI.
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON"}})

    messages = data.get("messages", [])
    if not messages:
        return JSONResponse(status_code=400, content={"error": {"message": "Missing messages"}})

    # Open Interpreter sendet eine Historie. Wir fassen sie für Ask Alma als Text zusammen:
    full_prompt = ""
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        full_prompt += f"[{role}]:\n{content}\n\n"

    # Browser die Arbeit machen lassen
    antwort_text = await alma_browser.send_message(full_prompt)

    # Die Antwort exakt nach der Spezifikation verpacken
    response_data = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model", "ask-alma-local"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": antwort_text
                },
                "finish_reason": "stop"
            }
        ]
    }

    return JSONResponse(content=response_data)

if __name__ == "__main__":
    print("Starte API-Server auf http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)