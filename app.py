"""
UK 49s Flask API Backend
=========================
Wraps uk49s_results.py and exposes JSON endpoints consumed by index.html.

Run:
    pip install flask flask-cors requests beautifulsoup4
    python app.py

Endpoints:
    GET  /api/results?draw=all|brunch|lunch|drive|tea&num=10
    POST /api/analyse   { numbers:[1..6], bonus:N, tse:"27" }
    GET  /api/health
"""

import itertools
import sys
import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Import the backend module (must live in the same directory)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
import uk49s_results as uk49s

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)


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

    # Set 4
    if tse is None:
        tse_val = str(sets["x"]["x4"])
    else:
        tse_val = str(tse).strip()

    d1 = int(tse_val[0]) if len(tse_val) > 0 and tse_val[0].isdigit() else 0
    d2 = int(tse_val[1]) if len(tse_val) > 1 and tse_val[1].isdigit() else 0
    S4 = [n for n in [d1, d2, d1 + d2] if 1 <= n <= 49]
    sets["S4"] = S4

    S1, S2, S3, S5 = sets["S1"], sets["S2"], sets["S3"], sets["S5"]
    all_sets   = [S1, S2, S3, S4, S5]
    set_labels = ["S1", "S2", "S3", "S4", "S5"]

    tagged = []
    for lbl, s in zip(set_labels, all_sets):
        for n in s:
            tagged.append({"number": n, "set": lbl, "colour": uk49s._colour_of(n)})

    # By colour
    colour_groups: dict = {}
    for item in tagged:
        colour_groups.setdefault(item["colour"], []).append(item)

    colour_analysis = []
    for colour in ["Red", "Orange", "Yellow", "Green", "Blue", "Brown", "Purple"]:
        items = colour_groups.get(colour, [])
        if len(items) >= 3:
            nums   = [i["number"] for i in items]
            combos = [list(c) for c in itertools.combinations(nums, 3)]
            colour_analysis.append({
                "colour":  colour,
                "numbers": items,
                "combos":  combos,
            })

    # By ending digit
    digit_groups: dict = {}
    for item in tagged:
        digit_groups.setdefault(item["number"] % 10, []).append(item)

    digit_analysis = []
    for digit in sorted(digit_groups.keys()):
        items = digit_groups[digit]
        if len(items) >= 3:
            nums   = [i["number"] for i in items]
            combos = [list(c) for c in itertools.combinations(nums, 3)]
            digit_analysis.append({
                "digit":   digit,
                "numbers": items,
                "combos":  combos,
            })

    return {
        "intermediates": sets["x"],
        "sets": {
            "S1": S1, "S2": S2, "S3": S3, "S4": S4, "S5": S5,
        },
        "tagged":          tagged,
        "colour_analysis": colour_analysis,
        "digit_analysis":  digit_analysis,
        "tse_used":        tse_val,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

DRAW_MAP = {
    "brunch": uk49s.DrawType.BRUNCHTIME,
    "lunch":  uk49s.DrawType.LUNCHTIME,
    "drive":  uk49s.DrawType.DRIVETIME,
    "tea":    uk49s.DrawType.TEATIME,
}


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@app.get("/api/results")
def get_results():
    """
    Query params:
        draw = all | brunch | lunch | drive | tea  (default: all)
        num  = 1-20                                 (default: 10)
    """
    draw_key = request.args.get("draw", "all").lower()
    num      = min(max(int(request.args.get("num", 10)), 1), 20)

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
            return jsonify({"error": f"Unknown draw type: {draw_key}"}), 400

        return jsonify({"ok": True, "data": payload})

    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/analyse")
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

    if not numbers or len(numbers) != 6:
        return jsonify({"ok": False, "error": "Provide exactly 6 main numbers"}), 400
    if bonus is None:
        return jsonify({"ok": False, "error": "Provide a bonus ball number"}), 400

    try:
        numbers = [int(n) for n in numbers]
        bonus   = int(bonus)
        if not all(1 <= n <= 49 for n in numbers + [bonus]):
            raise ValueError("All numbers must be between 1 and 49")

        result = _build_analysis(numbers, bonus, tse)
        return jsonify({"ok": True, "data": result})

    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# Serve the frontend
@app.get("/")
def index():
    return app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n UK 49s Web App")
    print(" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
