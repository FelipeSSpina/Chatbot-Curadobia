# -*- coding: utf-8 -*-
# file: code/webapi/main.py
# C�LULA 3 � FastAPI com CORS + /health + /api/chat + /api/stream (SSE)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio

app = FastAPI(title="Curadobia WebAPI")

# CORS: em dev liberado; em prod, restrinja para seu dom�nio/porta
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatIn(BaseModel):
    prompt: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/chat")
async def chat(body: ChatIn):
    # Troque por sua l�gica real (LLM/RAG). Aqui � s� eco.
    reply = f"Eco BIA: {body.prompt}"
    return {"reply": reply}

@app.get("/api/stream")
async def stream(request: Request, prompt: str):
    async def event_generator():
        for word in prompt.split():
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.05)
            yield {"event": "message", "data": word}
        yield {"event": "message", "data": "[[DONE]]"}
    return EventSourceResponse(event_generator())

