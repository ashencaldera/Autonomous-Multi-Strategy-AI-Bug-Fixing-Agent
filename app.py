"""
Flask Application
Serves the web UI and exposes the agent via REST + Server-Sent Events (SSE).

Endpoints:
  GET  /                → main page
  POST /api/fix         → start a fix session, returns session_id
  GET  /api/stream/<id> → SSE stream of agent events
  GET  /api/examples    → list of example buggy code snippets
  GET  /api/health      → health check
"""

from dotenv import load_dotenv
load_dotenv()  # Load .env file BEFORE config reads environment variables

import json
import logging
import os
import queue
import threading
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from config import config

# Logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# In-memory session store  {session_id: Queue}
_sessions: dict[str, queue.Queue] = {}
_sessions_lock = threading.Lock()

# ── Example snippets ──────────────────────────────────────────────────────────

EXAMPLES = [
    {
        "title": "Missing Colon (SyntaxError)",
        "code": 'def add(a, b)\n    return a + b\n\nprint(add(2, 3))',
    },
    {
        "title": "NameError — Undefined Variable",
        "code": 'def greet(name):\n    message = "Hello, " + nane\n    return message\n\nprint(greet("Alice"))',
    },
    {
        "title": "ZeroDivisionError",
        "code": 'def average(numbers):\n    total = sum(numbers)\n    return total / len(numbers)\n\nprint(average([]))',
    },
    {
        "title": "TypeError — Wrong Argument Type",
        "code": 'def double(x):\n    return x * 2\n\nresult = double("5")\nprint(result + 10)',
    },
    {
        "title": "IndexError — Out of Range",
        "code": 'items = [1, 2, 3]\n\ndef get_last(lst):\n    return lst[len(lst)]\n\nprint(get_last(items))',
    },
    {
        "title": "Indentation Error",
        "code": 'def factorial(n):\n    if n <= 1:\n        return 1\n   return n * factorial(n - 1)\n\nprint(factorial(5))',
    },
    {
        "title": "AttributeError",
        "code": 'name = "hello world"\nwords = name.split()\nresult = words.uppercase()\nprint(result)',
    },
    {
        "title": "Logic Error — Wrong Fibonacci",
        "code": 'def fibonacci(n):\n    if n <= 0:\n        return 0\n    elif n == 1:\n        return 1\n    return fibonacci(n - 1) + fibonacci(n - 3)\n\nprint(fibonacci(7))',
    },
]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/api/examples")
def examples():
    return jsonify(EXAMPLES)


@app.route("/api/fix", methods=["POST"])
def start_fix():
    """
    Accept buggy code, start a background agent session,
    return a session_id for the SSE stream.
    """
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()

    if not code:
        return jsonify({"error": "No code provided"}), 400

    if len(code) > config.MAX_CODE_LENGTH:
        return jsonify({
            "error": f"Code too long. Max {config.MAX_CODE_LENGTH} characters."
        }), 400

    session_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue(maxsize=200)

    with _sessions_lock:
        _sessions[session_id] = q

    # Start agent in background thread
    thread = threading.Thread(
        target=_run_agent,
        args=(session_id, code, q),
        daemon=True,
    )
    thread.start()

    return jsonify({"session_id": session_id})


@app.route("/api/stream/<session_id>")
def stream(session_id: str):
    """Server-Sent Events stream for a given session."""
    with _sessions_lock:
        q = _sessions.get(session_id)

    if q is None:
        return jsonify({"error": "Session not found"}), 404

    @stream_with_context
    def generate():
        while True:
            try:
                event = q.get(timeout=30)
                if event is None:  # sentinel — session done
                    # Clean up
                    with _sessions_lock:
                        _sessions.pop(session_id, None)
                    yield "event: close\ndata: {}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Keep-alive ping
                yield ": ping\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Background agent runner ───────────────────────────────────────────────────

def _run_agent(session_id: str, code: str, q: queue.Queue):
    """Run the agent in a background thread, pushing events to the queue."""
    try:
        # Import here to avoid circular imports
        from agent.controller import AgentController
        agent = AgentController()

        for event in agent.fix_stream(code):
            try:
                q.put(event, timeout=5)
            except queue.Full:
                logger.warning(f"Session {session_id}: queue full, dropping event")

    except Exception as e:
        logger.exception(f"Session {session_id}: agent crashed")
        q.put({
            "event": "error",
            "data": {"message": str(e)},
        })
    finally:
        q.put(None)  # sentinel


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is not set! Set it in your .env file.")
    else:
        logger.info("GROQ API key found ✓")

    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True,
    )