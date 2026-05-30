"""
UK 49s Flask API Backend
=========================
Wraps uk49s_results.py and exposes JSON endpoints consumed by index.html.

Run:
    pip install -r requirements.txt
    python app.py

Endpoints:
    GET  /api/results?draw=all|brunch|lunch|drive|tea&num=10
    POST /api/analyse   { numbers:[1..6], bonus:N, tse:"27" }
    GET  /api/health
"""

import itertools
import sys
import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# Import the backend module (must live in the same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
import uk49s_results as uk49s

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
PORT = int(os.getenv('PORT', 5000))
CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')  # For production, use RedisCache
CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))  # 5 minutes

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# Caching
cache = Cache(app, config={'CACHE_TYPE': CACHE_TYPE, 'CACHE_DEFAULT_TIMEOUT': CACHE_DEFAULT_TIMEOUT})

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Logging
logging.basicConfig(level=logging.INFO if DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Draw map config
DRAW_MAP = {
    "breakfast": uk49s.DrawType.BREAKFASTTIME,
    "brunch":    uk49s.DrawType.BRUNCHTIME,
    "lunch":     uk49s.DrawType.LUNCHTIME,
    "drive":     uk49s.DrawType.DRIVETIME,
    "tea":       uk49s.DrawType.TEATIME,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialise_result(r: uk49s.DrawResult) -> dict:
    return {
        "draw_type":  r.draw_type.value,
        "date":       r.date,
        "numbers":    r.numbers,
        "bonus_ball": r.bonus_ball,
    }


def _build_analysis(numbers: list, bonus: int, tse: str | None) -> dict:
    """Run the analyser and return a JSON-serialisable dict."""
    sets = uk49s._build_sets(numbers, bonus)

    return {
        "variables": sets["x"]
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    logger.info("Health check requested")
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT, query_string=True)
@app.get("/api/results")
@limiter.limit("10 per minute")
def get_results():
    """
    Query params:
        draw = all | brunch | lunch | drive | tea  (default: all)
        num  = 1-20                                 (default: 10)
    """
    draw_key = request.args.get("draw", "all").lower()
    num      = min(max(int(request.args.get("num", 10)), 1), 20)

    logger.info(f"Results requested: draw={draw_key}, num={num}")

    try:
        if draw_key == "all":
            all_res = uk49s.get_all_draws(num_draws=num)
            payload = {}
            for dt in uk49s.DrawType:
                payload[dt.value] = [_serialise_result(r) for r in all_res.get(dt)]
        elif draw_key in DRAW_MAP:
            dt      = DRAW_MAP[draw_key]
            results = uk49s.get_draw_results(dt, num_draws=num)
            payload = {dt.value: [_serialise_result(r) for r in results]}
        else:
            logger.warning(f"Unknown draw type: {draw_key}")
            return jsonify({"error": f"Unknown draw type: {draw_key}"}), 400

        return jsonify({"ok": True, "data": payload})

    except RuntimeError as exc:
        logger.error(f"Runtime error in get_results: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception as exc:
        logger.error(f"Unexpected error in get_results: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/analyse")
@limiter.limit("5 per minute")
def post_analyse():
    """
    Body (JSON):
        numbers  : [n1, n2, n3, n4, n5, n6]   required
        bonus    : int                          required
        tse      : "27"                         optional
    """
    body = request.get_json(force=True, silent=True) or {}

    numbers = body.get("numbers")
    bonus   = body.get("bonus")
    tse     = body.get("tse") or None

    logger.info(f"Analysis requested: numbers={numbers}, bonus={bonus}, tse={tse}")

    if not numbers or len(numbers) != 6:
        logger.warning("Invalid numbers input")
        return jsonify({"ok": False, "error": "Provide exactly 6 main numbers"}), 400
    if bonus is None:
        logger.warning("Missing bonus ball")
        return jsonify({"ok": False, "error": "Provide a bonus ball number"}), 400

    try:
        numbers = [int(n) for n in numbers]
        bonus   = int(bonus)
        if not all(1 <= n <= 49 for n in numbers + [bonus]):
            raise ValueError("All numbers must be between 1 and 49")
        # Sanitize TSE
        if tse:
            import re
            if not re.match(r'^\d{1,2}$', str(tse)):
                raise ValueError("TSE must be a 1-2 digit number")

        result = _build_analysis(numbers, bonus, tse)
        return jsonify({"ok": True, "data": result})

    except (ValueError, TypeError) as exc:
        logger.warning(f"Validation error: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Unexpected error in post_analyse: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500


# Serve the frontend
@app.get("/")
def index():
    return app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n UK 49s Web App")
    print(f" Open http://localhost:{PORT} in your browser\n")
    app.run(debug=DEBUG, port=PORT)
