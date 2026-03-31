import os
import json
import boto3
import logging
import sys
import time
import asyncio
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, AsyncGenerator, Dict, List

logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
logger = logging.getLogger("bedrock-proxy")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

REQUIRED_TOKEN = "sfl-token-llm-very-secret"
AWS_REGION = os.getenv("AWS_REGION", "eu-south-1")
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)


def normalize_messages(body: Dict[str, Any]) -> tuple:
    model_id = body.get("model", "qwen.qwen3-coder-30b-a3b-v1:0")
    raw = body.get("messages", []) or ([{"role": "user", "content": body["prompt"]}] if "prompt" in body else [])
    system_prompts, temp = [], []
    for m in raw:
        role, content = str(m.get("role", "user")).lower(), m.get("content", "")
        if role == "system": system_prompts.append({"text": content})
        else: temp.append({"role": role if role in ["user", "assistant"] else "user", "content": [{"text": content}]})
    while temp and temp[0]["role"] != "user": temp.pop(0)
    final = []
    if temp:
        curr = temp[0]
        for nxt in temp[1:]:
            if nxt["role"] == curr["role"]: curr["content"][0]["text"] += "\n" + nxt["content"][0]["text"]
            else: final.append(curr); curr = nxt
        final.append(curr)
    return model_id, system_prompts, final or [{"role": "user", "content": [{"text": "Continue"}]}]

async def responses_sse_generator(model_id: str, system: List, messages: List, config: Dict) -> AsyncGenerator[str, None]:
    try:
        resp_id = f"resp_{int(time.time())}"
        
        # 1. SEND response.created (con metadata)
        ev_created = {"type": "response.created", "response": {"id": resp_id, "status": "in_progress"}}
        yield f"data: {json.dumps(ev_created)}\n\n"
        print(f"OUT -> data: {json.dumps(ev_created)}", flush=True)
        await asyncio.sleep(0.02)

        response = bedrock_runtime.converse_stream(modelId=model_id, messages=messages, system=system, inferenceConfig=config)
        
        text_started = False
        accumulated_text = ""
        output_index = 0
        content_index = 0

        # Initial events for Codex format
        ev_item_added = {"type": "response.output_item.added", "output_index": output_index, "item": {"type": "message", "role": "assistant", "content": []}}
        yield f"data: {json.dumps(ev_item_added)}\n\n"
        print(f"OUT -> data: {json.dumps(ev_item_added)}", flush=True)
        await asyncio.sleep(0.02)

        ev_content_part_added = {"type": "response.content_part.added", "output_index": output_index, "content_index": content_index, "part": {"type": "output_text", "text": ""}}
        yield f"data: {json.dumps(ev_content_part_added)}\n\n"
        print(f"OUT -> data: {json.dumps(ev_content_part_added)}", flush=True)
        await asyncio.sleep(0.02)

        for event in response.get("stream"):
            if "contentBlockDelta" in event:
                text = event["contentBlockDelta"]["delta"]["text"]
                if text:
                    text_started = True
                    accumulated_text += text
                    ev_delta = {"type": "response.output_text.delta", "output_index": output_index, "content_index": content_index, "delta": text}
                    yield f"data: {json.dumps(ev_delta)}\n\n"
                    print(f"OUT -> data: {json.dumps(ev_delta)}", flush=True)
            
            elif "contentBlockDone" in event:
                if text_started:
                    # Final events for Codex format
                    ev_text_done = {"type": "response.output_text.done", "output_index": output_index, "content_index": content_index, "text": accumulated_text}
                    yield f"data: {json.dumps(ev_text_done)}\n\n"
                    print(f"OUT -> data: {json.dumps(ev_text_done)}", flush=True)
                    await asyncio.sleep(0.02)

                    ev_content_part_done = {"type": "response.content_part.done", "output_index": output_index, "content_index": content_index, "part": {"type": "output_text", "text": accumulated_text}}
                    yield f"data: {json.dumps(ev_content_part_done)}\n\n"
                    print(f"OUT -> data: {json.dumps(ev_content_part_done)}", flush=True)
                    await asyncio.sleep(0.02)

                    ev_output_item_done = {"type": "response.output_item.done", "output_index": output_index, "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": accumulated_text}]}}
                    yield f"data: {json.dumps(ev_output_item_done)}\n\n"
                    print(f"OUT -> data: {json.dumps(ev_output_item_done)}", flush=True)
                    await asyncio.sleep(0.02)

                    text_started = False
                    
        # 4. SEND response.completed (con metadata e status)
        ev_completed = {"type": "response.completed", "response": {"id": resp_id, "status": "completed"}}
        yield f"data: {json.dumps(ev_completed)}\n\n"
        print(f"OUT -> data: {json.dumps(ev_completed)}", flush=True)
        await asyncio.sleep(0.02)

        # 5. SEND [DONE]
        yield "data: [DONE]\n\n"
        print("OUT -> data: [DONE]", flush=True)
        
        # 6. WAIT (200ms) per garantire il flush dei buffer TCP prima di chiudere il generatore
        await asyncio.sleep(0.2)

    except Exception as e:
        logger.error(f"SSE Error: {e}")
        err_ev = {"type": "error", "error": {"message": str(e)}}
        yield f"data: {json.dumps(err_ev)}\n\n"
        print(f"OUT -> data: {json.dumps(err_ev)}", flush=True)
        yield "data: [DONE]\n\n"
        await asyncio.sleep(0.2)

@app.post("/v1/responses")
@app.post("/responses")
async def responses_handler(request: Request):
    auth = request.headers.get("Authorization", "")
    if f"Bearer {REQUIRED_TOKEN}" not in auth: raise HTTPException(status_code=403)
    body = await request.json()
    print(f"IN <- {json.dumps(body)}", flush=True)
    model_id, system, msgs = normalize_messages(body)
    return StreamingResponse(
        responses_sse_generator(model_id, system, msgs, {"maxTokens": 4096, "temperature": 0.1}), 
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_handler(request: Request):
    auth = request.headers.get("Authorization", "")
    if f"Bearer {REQUIRED_TOKEN}" not in auth: raise HTTPException(status_code=403)
    body = await request.json()
    model_id, system, msgs = normalize_messages(body)
    async def gen():
        res = bedrock_runtime.converse_stream(modelId=model_id, messages=msgs, system=system, inferenceConfig={"maxTokens": 4096})
        for ev in res.get("stream"):
            if "contentBlockDelta" in ev:
                t = ev["contentBlockDelta"]["delta"]["text"]
                if t: yield f"data: {json.dumps({'choices': [{'delta': {'content': t}}]})}\n\n"
        yield "data: [DONE]\n\n"
        await asyncio.sleep(0.2)
    return StreamingResponse(gen(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
