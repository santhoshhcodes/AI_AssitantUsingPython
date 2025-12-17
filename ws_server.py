# # ws_server.py

# import asyncio
# import websockets
# import json
# import base64
# import os
# import uuid
# import logging

# from whisper_wrapper import transcribe_audio
# from piper_tts import synthesize

# # Hybrid pieces
# from ai_agent.intent_engine import detect_intent
# from ai_agent.agent import generate_reply
# from ai_agent.llm_agent import call_llm

# HOST = "0.0.0.0"
# PORT = int(os.environ.get("WS_PORT", 8000))
# TTS_ENABLED = os.environ.get("ENABLE_TTS", "1") != "0"
# STT_TEMP_DIR = os.environ.get("TMP_DIR", "./tmp")
# MAX_AUDIO_FILE_BYTES = 20 * 1024 * 1024

# # Confidence threshold (if LLM confidence > this and rule-based didn't match, accept LLM intent)
# LLM_CONFIDENCE_THRESHOLD = float(os.environ.get("LLM_CONFIDENCE_THRESHOLD", 0.6))

# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# logger = logging.getLogger("ws_server")

# # ensure temp dir exists early
# try:
#     if not os.path.exists(STT_TEMP_DIR):
#         os.makedirs(STT_TEMP_DIR, exist_ok=True)
#         logger.info("Created STT temp dir: %s", STT_TEMP_DIR)
# except Exception as e:
#     logger.exception("Failed to create STT temp dir %s: %s", STT_TEMP_DIR, e)


# def _safe_write_tempfile(b: bytes, suffix: str = ".wav") -> str:
#     fn = f"{STT_TEMP_DIR}/temp_{uuid.uuid4().hex}{suffix}"
#     with open(fn, "wb") as f:
#         f.write(b)
#     return fn


# def _safe_remove(fn: str):
#     try:
#         if os.path.exists(fn):
#             os.remove(fn)
#     except Exception:
#         pass


# async def _process_user_text(ws, user_text: str, want_voice_reply: bool = False):
#     """
#     Hybrid processing:
#     - Try rule-based intent detection first.
#     - If rule matched with high confidence -> agent handles (deterministic).
#     - Else call LLM and decide based on LLM confidence.
#     - Always produce a reply string; if intent is actionable and confidence high, agent executes deterministic reply text.
#     """

#     # default intent object so later code can reference it safely
#     intent = {"intent": None, "params": {}}
#     used_source = "none"
#     confidence = 0.0

#     # 1) rule-based detection
#     rule = None
#     try:
#         rule = detect_intent(user_text)
#     except Exception as e:
#         logger.exception("Rule-based intent detection failed: %s", e)
#         rule = None

#     # If strong rule match, use it
#     if rule and rule.get("confidence", 0.0) >= 0.7:
#         intent = {"intent": rule["intent"], "params": rule.get("params", {})}
#         reply = generate_reply(user_text, intent=intent)
#         confidence = float(rule.get("confidence", 0.0))
#         used_source = "rule"
#     else:
#         # Fallback to LLM
#         llm = call_llm(user_text)
#         llm_intent = llm.get("intent")
#         llm_conf = float(llm.get("confidence") or 0.0)
#         llm_reply_text = llm.get("reply", "")

#         # Use LLM intent when confidence >= threshold and intent is actionable
#         if llm_conf >= LLM_CONFIDENCE_THRESHOLD and llm_intent and llm_intent != "unknown":
#             intent = {"intent": llm_intent, "params": llm.get("params", {})}
#             # prefer agent deterministic handling for supported intents
#             reply_from_agent = generate_reply(user_text, intent=intent)
#             reply = reply_from_agent or llm_reply_text
#             confidence = llm_conf
#             used_source = "llm_high_conf"
#         else:
#             # Agent fallback (legacy rules)
#             reply = generate_reply(user_text, intent=None)
#             confidence = llm_conf
#             if reply.startswith("Sorry, I did not understand") and llm_reply_text:
#                 # prefer LLM reply when agent fallback is generic
#                 reply = llm_reply_text
#                 used_source = "llm_low_conf_reply"
#             else:
#                 used_source = "agent_fallback"

#     # TTS if requested + enabled
#     audio_b64 = ""
#     if want_voice_reply and TTS_ENABLED and reply:
#         try:
#             audio_b64 = synthesize(reply)
#         except Exception:
#             logger.exception("TTS error")
#             audio_b64 = ""

#     payload = {
#         "type": "reply",
#         "text": user_text,
#         "reply": reply,
#         "audio": audio_b64,
#         "intent": intent.get("intent"),
#         "params": intent.get("params", {}),
#         "meta": {"source": used_source, "confidence": confidence}
#     }

#     await ws.send(json.dumps(payload))


# async def _handle_text(ws, user_text: str):
#     await _process_user_text(ws, user_text, want_voice_reply=False)


# async def _handle_audio(ws, audio_b64: str, want_voice_reply: bool):
#     try:
#         audio_bytes = base64.b64decode(audio_b64)
#     except Exception:
#         await ws.send(json.dumps({"type": "error", "message": "Invalid audio"}))
#         return

#     if len(audio_bytes) > MAX_AUDIO_FILE_BYTES:
#         await ws.send(json.dumps({"type": "error", "message": "Audio too large"}))
#         return

#     filename = None
#     try:
#         filename = _safe_write_tempfile(audio_bytes)
#         try:
#             text = transcribe_audio(filename)
#         except Exception:
#             logger.exception("STT error")
#             text = ""

#         if not text:
#             await ws.send(json.dumps({
#                 "type": "reply",
#                 "text": "",
#                 "reply": "I could not hear anything clearly. Please try again.",
#                 "audio": "",
#                 "intent": None,
#                 "params": {},
#                 "meta": {"source": "stt_failed", "confidence": 0.0}
#             }))
#             return

#         # Process the transcribed text (same as typed text)
#         await _process_user_text(ws, text, want_voice_reply=want_voice_reply)

#     finally:
#         if filename:
#             _safe_remove(filename)


# # NOTE: many websocket versions pass both (websocket, path) into handler
# # Use signature with (ws, path) to be compatible
# async def handler(ws):
#     client_addr = None
#     try:
#         # older websockets server exposed remote_address on the websocket object
#         client_addr = getattr(ws, "remote_address", None)
#     except Exception:
#         client_addr = None

#     logger.info("Client connected: %s", client_addr)
#     try:
#         async for msg in ws:
#             try:
#                 data = json.loads(msg)
#             except Exception:
#                 await ws.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
#                 continue

#             msg_type = data.get("type")
#             if msg_type == "connect":
#                 await ws.send(json.dumps({"type": "status", "content": "Connected to Hybrid Python AI Backend"}))
#             elif msg_type == "text":
#                 await _handle_text(ws, data.get("text", ""))
#             elif msg_type == "audio":
#                 await _handle_audio(ws, data.get("audio", ""), want_voice_reply=True)
#             elif msg_type == "audio_to_text":
#                 await _handle_audio(ws, data.get("audio", ""), want_voice_reply=False)
#             else:
#                 await ws.send(json.dumps({"type": "error", "message": f"Unknown message type '{msg_type}'"}))

#     except websockets.exceptions.ConnectionClosedOK:
#         logger.info("Client closed connection (OK)")
#     except websockets.exceptions.ConnectionClosedError as e:
#         logger.warning("Connection closed with error: %s", e)
#     except Exception:
#         logger.exception("Unhandled exception in handler")
#     finally:
#         logger.info("Client disconnected: %s", client_addr)


# async def main():
#     # Bind server
#     server = await websockets.serve(handler, HOST, PORT)
#     logger.info("WebSocket server listening on ws://%s:%s", HOST, PORT)
#     try:
#         await server.wait_closed()
#     except asyncio.CancelledError:
#         logger.info("Server cancelled, shutting down")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         logger.info("Server stopped by user")
