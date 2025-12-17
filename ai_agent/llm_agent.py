import os, json
from dotenv import load_dotenv

load_dotenv()

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = """
You are an enterprise-grade AI business assistant for Eveready Tirupur.

You operate INSIDE a multi-layer AI system that includes:
- Rule-based intent detection
- Deterministic business logic
- Vector search (FAISS)
- You are the FINAL fallback only

==============================
WHAT YOU WILL RECEIVE
==============================

1) User message (natural language)
2) VERIFIED BUSINESS DATA (JSON)
   - May include ZERO, ONE, or MULTIPLE records
   - This data is the ONLY source of truth

==============================
ABSOLUTE RULES (CRITICAL)
==============================

- NEVER repeat or rephrase answers already handled by rules
- NEVER override deterministic agent responses
- NEVER hallucinate, infer, or guess missing data
- NEVER merge multiple records
- NEVER assume intent
- NEVER respond if data is insufficient — ask for clarification instead
- NEVER generate navigation or UI actions

If you are unsure → ASK, do NOT ANSWER.

==============================
WHEN YOU ARE ALLOWED TO RESPOND
==============================

You may respond ONLY when:
- Rule-based intent handling did NOT return a reply
- You are given VERIFIED BUSINESS DATA or asked for reasoning
- You are explicitly required to analyze, clarify, or explain

If a rule-based reply already exists → RETURN A MINIMAL CONFIRMATION OR NOTHING.

==============================
EMPLOYEE DATA DECISION LOGIC
==============================

STEP 1: Count employee records in JSON

CASE A: ZERO records
→ Respond: employee not found
→ Ask user to refine query

CASE B: EXACTLY ONE record
→ Respond using ONLY that record
→ No additional assumptions

CASE C: MULTIPLE records
→ DO NOT choose one
→ Ask user to clarify (EmpNo / Department / Designation)

==============================
ANALYSIS & SUGGESTIONS
==============================

If data is sufficient:
- You may summarize
- You may compare
- You may suggest improvements
- You may highlight risks or trends

If data is NOT sufficient:
- Clearly say so
- Ask what additional data is required

==============================
STYLE & TONE
==============================

- Professional
- Concise
- Business-focused
- No repetition
- No storytelling
- No emojis
- No apologies unless an error occurred

==============================
OUTPUT FORMAT (JSON ONLY)
==============================

Return ONLY valid JSON:

{
  "intent": "employee_info | clarification_needed | not_found | analysis | general",
  "params": {},
  "reply": "Final response to user",
  "confidence": 0.0
}

CONFIDENCE RULES:
- >0.85 → exact single-record answer
- 0.5–0.7 → clarification required
- <0.5 → insufficient data
"""


# =========================
# GROQ SETUP
# =========================
GROQ_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"

_has_groq = False
client = None

if GROQ_KEY:
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_KEY)
        _has_groq = True
    except:
        _has_groq = False


# =========================
# SAFE JSON PARSER
# =========================
def safe_parse_json(txt):
    """Parse JSON from LLM response. Handles markdown wrapping."""
    try:
        return json.loads(txt)
    except:
        try:
            # Extract JSON from markdown
            s, e = txt.find("{"), txt.rfind("}")
            if s >= 0 and e > s:
                return json.loads(txt[s : e + 1])
        except:
            pass

    # Fallback
    return {
        "intent": "unknown",
        "params": {},
        "reply": "I didn't understand. Please try again.",
        "confidence": 0.0,
    }


# =========================
# MAIN AI CALL (WITH CONTEXT)
# =========================
def call_llm(user_text: str, business_context=None):
    """
    user_text       → user's question
    business_context→ real data from backend (employee, sales, stock, etc.)
    """

    if not _has_groq:
        return {
            "intent": "unknown",
            "params": {},
            "reply": "AI service unavailable.",
            "confidence": 0.0,
        }

    context_block = ""
    try:
        if business_context and isinstance(business_context, dict):
            context_block = f"""
VERIFIED BUSINESS DATA (JSON):
{json.dumps(business_context, indent=2)}
"""
    except Exception as e:
        print(f"Context serialization error: {e}")
        context_block = ""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
USER QUESTION:
{user_text}

{context_block}
""",
        },
    ]

    try:
        # Validate input
        if not user_text or not user_text.strip():
            return {
                "intent": "unknown",
                "params": {},
                "reply": "I didn't catch that. Could you please repeat?",
                "confidence": 0.0,
            }

        # Call LLM
        res = client.chat.completions.create(
            model=GROQ_MODEL, messages=messages, temperature=0.2, max_tokens=400
        )

        # Handle response
        if res and res.choices and len(res.choices) > 0:
            llm_response = res.choices[0].message.content
            parsed = safe_parse_json(llm_response)

            # Validate reply exists
            if parsed and parsed.get("reply"):
                return parsed
            else:
                return {
                    "intent": "unknown",
                    "params": {},
                    "reply": "Could not generate response. Try again.",
                    "confidence": 0.0,
                }
        else:
            return {
                "intent": "unknown",
                "params": {},
                "reply": "No response from AI service.",
                "confidence": 0.0,
            }

    except Exception as e:
        print(f"LLM call error: {e}")
        return {
            "intent": "unknown",
            "params": {},
            "reply": "I encountered an issue. Please try again.",
            "confidence": 0.0,
        }
