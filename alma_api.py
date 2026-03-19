import asyncio
import time
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
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
        print("[Browser] Starte Playwright...")
        self.playwright = await async_playwright().start()
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
        if not self.is_ready:
            return "Fehler: Browser ist noch nicht bereit."

        try:
            print(f"[Browser] Sende Nachricht ({len(text)} Zeichen)...")
            
            eingabefeld = self.page.locator("textarea").first
            antwort_locator = self.page.locator(".markdown-body")
            
            anzahl_vorher = await antwort_locator.count()
            
            await eingabefeld.fill(text)
            await self.page.keyboard.press("Enter")
            
            neue_antwort_index = anzahl_vorher
            start_wait = time.time()
            
            while await antwort_locator.count() <= anzahl_vorher:
                if time.time() - start_wait > 30:
                    return "Fehler: KI hat nach 30 Sekunden nicht geantwortet."
                await asyncio.sleep(0.5)
                
            das_neue_element = antwort_locator.nth(neue_antwort_index)
            letzter_text = ""
            gleicher_text_zaehler = 0
            
            start_stream = time.time()
            max_total_wait = 180 
            
            while time.time() - start_stream < max_total_wait:
                aktueller_text = await das_neue_element.inner_text()
                
                if aktueller_text == letzter_text and aktueller_text.strip() != "":
                    gleicher_text_zaehler += 1
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
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON"}})

    messages = data.get("messages", [])
    if not messages:
        return JSONResponse(status_code=400, content={"error": {"message": "Missing messages"}})

    # Open Interpreter sendet einen 'stream' Parameter
    is_stream = data.get("stream", False)

    # Prompt zusammenbauen
    full_prompt = ""
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        full_prompt += f"[{role}]:\n{content}\n\n"

    # Browser die Arbeit machen lassen
    antwort_text = await alma_browser.send_message(full_prompt)

    # --- FAKE STREAMING FÜR OPEN INTERPRETER ---
    if is_stream:
        async def stream_generator():
            # 1. Wir senden den gesamten Text als einen großen "Stream-Chunk"
            chunk = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("model", "ask-alma-local"),
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": antwort_text}, "finish_reason": None}]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            
            # 2. Wir senden das Signal, dass der Stream beendet ist
            stop_chunk = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("model", "ask-alma-local"),
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(stop_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # --- STANDARD ANTWORT (falls ohne Stream angefragt) ---
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