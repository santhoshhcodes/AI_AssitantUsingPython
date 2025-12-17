import asyncio
import json
import base64
import os
import uuid
import logging
from typing import Optional

import websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# =========================
# IMPORT YOUR EXISTING LOGIC
# =========================
from whisper_wrapper import transcribe_audio
from piper_tts import synthesize

from ai_agent.intent_engine import detect_intent
from ai_agent.agent import generate_reply
from ai_agent.llm_agent import call_llm

from database.employeeDetails import router as employeeDetails_router
from database.getEmployees import router as getEmployees_router
from database.report import router as report_router


from ai_agent.employee_store import EmployeeVectorStore
import requests


from database.database import get_db, DATABASES
from sqlalchemy import text


# =========================
# CONFIG
# =========================
HOST = "0.0.0.0"
WS_PORT = int(os.environ.get("WS_PORT", 8000))
HTTP_PORT = int(os.environ.get("HTTP_PORT", 8001))

TTS_ENABLED = os.environ.get("ENABLE_TTS", "1") != "0"
STT_TEMP_DIR = os.environ.get("TMP_DIR", "./tmp")
MAX_AUDIO_FILE_BYTES = 20 * 1024 * 1024
LLM_CONFIDENCE_THRESHOLD = float(os.environ.get("LLM_CONFIDENCE_THRESHOLD", 0.6))

employee_store = EmployeeVectorStore()


# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("hybrid_server")

# =========================
# ENSURE TEMP DIR
# =========================
os.makedirs(STT_TEMP_DIR, exist_ok=True)

# =========================
# FASTAPI APP
# =========================
app = FastAPI(title="Hybrid AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employeeDetails_router, prefix="/api", tags=["employeeDetails"])
app.include_router(getEmployees_router, prefix="/api", tags=["getEmployees_router"])
app.include_router(report_router, prefix="/api", tags=["reports"])


@app.get("/")
def root():
    return {"message": "Hybrid AI Backend Running"}


# =========================
# UTIL FUNCTIONS
# =========================
def _safe_write_tempfile(b: bytes, suffix=".wav") -> str:
    path = f"{STT_TEMP_DIR}/audio_{uuid.uuid4().hex}{suffix}"
    with open(path, "wb") as f:
        f.write(b)
    return path


def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# =========================
# CORE AI PROCESSOR
# =========================
# =========================
# CORE AI PROCESSOR


async def process_text(ws, user_text: str, want_voice_reply: bool):
    try:
        heard_text = user_text

        # 0️⃣ EMPTY INPUT
        if not user_text or not user_text.strip():
            await ws.send(json.dumps({
                "type": "reply",
                "reply": "I didn’t hear anything. Please try again.",
                "text": heard_text,
                "intent": None,
                "params": {},
                "meta": {"source": "system", "confidence": 0.0},
            }))
            return

        # 1️⃣ INTENT DETECTION
        try:
            intent = detect_intent(user_text)
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            intent = None

        # 2️⃣ RULE ENGINE (HIGH CONFIDENCE)
        if intent and intent.get("confidence", 0) >= 0.85:
            try:
                reply = generate_reply(user_text, intent=intent) or ""
            except Exception as e:
                logger.error(f"Generate reply failed: {e}")
                reply = "I encountered an issue processing your request."

            if reply:
                audio_b64 = None

                if want_voice_reply and TTS_ENABLED:
                    try:
                        audio_b64 = synthesize(reply)
                    except Exception as e:
                        logger.error(f"TTS error: {e}")
                        audio_b64 = None

                await ws.send(json.dumps({
                    "type": "reply",
                    "reply": reply,
                    "text": heard_text,
                    "audio": audio_b64,
                    "intent": intent.get("intent"),
                    "params": intent.get("params", {}),
                    "meta": {
                        "source": "rule",
                        "confidence": intent.get("confidence", 0.85),
                    },
                }))
                return

        # 3️⃣ FAISS SEARCH
        try:
            employees = employee_store.search(user_text, top_k=5) or []
        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            employees = []

        business_context = {"employees": employees} if employees else None
        source = "faiss" if employees else "llm"

        # 4️⃣ LLM FALLBACK
        try:
            llm = call_llm(
                user_text=user_text,
                business_context=business_context
            ) or {}
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            llm = {}

        reply = llm.get("reply") or "I couldn't process that request."
        llm_intent = llm.get("intent")
        llm_params = llm.get("params", {})
        llm_confidence = llm.get("confidence", 0.0)

        audio_b64 = None
        if want_voice_reply and TTS_ENABLED:
            try:
                audio_b64 = synthesize(reply)
            except Exception as e:
                logger.error(f"TTS error: {e}")
                audio_b64 = None

        await ws.send(json.dumps({
            "type": "reply",
            "reply": reply,
            "text": heard_text,
            "audio": audio_b64,
            "intent": llm_intent,
            "params": llm_params,
            "meta": {
                "source": source,
                "confidence": llm_confidence,
            },
        }))

    except Exception:
        logger.exception("Process text fatal error")
        try:
            await ws.send(json.dumps({
                "type": "error",
                "message": "An unexpected error occurred.",
                "meta": {"confidence": 0.0},
            }))
        except:
            pass


# =========================
# WEBSOCKET HANDLER
# =========================
async def ws_handler(ws, path=None):

    logger.info("WebSocket connected: %s", ws.remote_address)

    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
                msg_type = data.get("type")

                if msg_type == "connect":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "status",
                                "content": "Connected to Hybrid AI Backend",
                            }
                        )
                    )

                elif msg_type == "text":
                    user_text = data.get("text", "").strip()
                    await process_text(ws, user_text, False)

                elif msg_type == "audio":
                    try:
                        audio_data = data.get("audio", "")
                        if not audio_data:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "error",
                                        "message": "No audio data received",
                                    }
                                )
                            )
                            continue

                        audio_bytes = base64.b64decode(audio_data)
                        if len(audio_bytes) > MAX_AUDIO_FILE_BYTES:
                            await ws.send(
                                json.dumps(
                                    {"type": "error", "message": "Audio file too large"}
                                )
                            )
                            continue

                        path = _safe_write_tempfile(audio_bytes)
                        try:
                            text = transcribe_audio(path) or ""
                            await process_text(ws, text, True)
                        finally:
                            _safe_remove(path)
                    except Exception as e:
                        logger.error(f"Audio processing error: {e}")
                        await ws.send(
                            json.dumps(
                                {"type": "error", "message": "Failed to process audio"}
                            )
                        )

                elif msg_type == "audio_to_text":
                    try:
                        audio_data = data.get("audio", "")
                        if not audio_data:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "error",
                                        "message": "No audio data received",
                                    }
                                )
                            )
                            continue

                        audio_bytes = base64.b64decode(audio_data)
                        if len(audio_bytes) > MAX_AUDIO_FILE_BYTES:
                            await ws.send(
                                json.dumps(
                                    {"type": "error", "message": "Audio file too large"}
                                )
                            )
                            continue

                        path = _safe_write_tempfile(audio_bytes)
                        try:
                            text = transcribe_audio(path) or ""
                            await process_text(ws, text, False)
                        finally:
                            _safe_remove(path)
                    except Exception as e:
                        logger.error(f"Audio to text error: {e}")
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "error",
                                    "message": "Failed to transcribe audio",
                                }
                            )
                        )

                else:
                    await ws.send(
                        json.dumps({"type": "error", "message": "Unknown message type"})
                    )

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                await ws.send(
                    json.dumps({"type": "error", "message": "Invalid message format"})
                )
            except Exception as e:
                logger.error(f"Message handling error: {e}")
                await ws.send(
                    json.dumps({"type": "error", "message": "Error processing message"})
                )

    except Exception:
        logger.exception("WebSocket error")
    finally:
        logger.info("WebSocket disconnected: %s", ws.remote_address)


# =========================
# RUN BOTH SERVERS
# =========================
def build_employee_index():
    try:
        res = requests.get(
            "http://127.0.0.1:8001/api/employees", params={"limit": 50, "offset": 0}
        )

        employees = res.json().get("data", [])

        if employees:
            employee_store.build(employees)
            logger.info("FAISS index built with %d employees", len(employees))
        else:
            logger.warning("No employees found for FAISS")

    except Exception as e:
        logger.exception("FAISS build failed: %s", e)


def build_employee_index_from_db():
    employees = []

    for db_key in DATABASES.keys():
        db = next(get_db(db_key))

        rows = db.execute(
            text(
                """
            SELECT EmpNo, EmployeeMobile, FirstName, Designation, DeptName
            FROM Employee_Mst
        """
            )
        ).fetchall()

        for r in rows:
            emp = dict(r._mapping)
            emp["db_key"] = db_key
            employees.append(emp)

    if employees:
        employee_store.build(employees)
        logger.info("FAISS built with %d employees", len(employees))
    else:
        logger.warning("No employees found for FAISS")


async def start_servers():
    import uvicorn

    build_employee_index_from_db()

    ws_server = await websockets.serve(ws_handler, HOST, WS_PORT)
    logger.info("WebSocket running on ws://%s:%s", HOST, WS_PORT)

    config = uvicorn.Config(
        app,
        host=HOST,
        port=HTTP_PORT,
        loop="asyncio",
        lifespan="off",
        log_level="info",
    )

    server = uvicorn.Server(config)

    await server.serve()


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    asyncio.run(start_servers())
