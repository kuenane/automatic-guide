"""
UK 49s Results Scraper + Draw Analyser
=======================================
Fetches the last 10 winning draws for each UK 49s draw type, then runs
a number-prediction analysis on any draw's most recent result.

Draw types & UK times:
  Brunchtime  11:49 AM  (launched Jan 2026)
  Lunchtime   12:49 PM
  Drivetime    4:49 PM
  Teatime      5:49 PM

Usage (CLI):
    python uk49s_results.py                        # fetch all draws
    python uk49s_results.py --draw lunch           # lunchtime only
    python uk49s_results.py --analyse              # fetch all + run analyser
    python uk49s_results.py --draw tea --analyse   # teatime + analyser
    python uk49s_results.py --manual               # analyser only (manual input)
    python uk49s_results.py --draw lunch --analyse --tse 27

Usage (import):
    from uk49s_results import get_all_draws, get_draw_results, DrawType, analyse

Requirements:
    pip install requests beautifulsoup4
"""

import re
import sys
import argparse
import itertools
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ===========================================================================
# Draw types
# ===========================================================================

class DrawType(Enum):
    BRUNCHTIME = "brunchtime"
    LUNCHTIME  = "lunchtime"
    DRIVETIME  = "drivetime"
    TEATIME    = "teatime"

DRAW_LABELS = {
    DrawType.BRUNCHTIME: "Brunchtime (11:49 AM UK)",
    DrawType.LUNCHTIME:  "Lunchtime  (12:49 PM UK)",
    DrawType.DRIVETIME:  "Drivetime  ( 4:49 PM UK)",
    DrawType.TEATIME:    "Teatime    ( 5:49 PM UK)",
}


# ===========================================================================
# Data models
# ===========================================================================

@dataclass
class DrawResult:
    """A single UK 49s draw result."""
    draw_type:  DrawType
    date:       str
    numbers:    list          # 6 main balls, sorted ascending
    bonus_ball: Optional[int] = None

    def __str__(self):
        nums  = "  ".join(f"{n:2d}" for n in self.numbers)
        bonus = f"  |  Bonus: {self.bonus_ball:2d}" if self.bonus_ball is not None else ""
        return f"{self.date}\n    Numbers: {nums}{bonus}"


@dataclass
class AllDrawResults:
    """Container for results from all four draw types."""
    brunchtime: list = field(default_factory=list)
    lunchtime:  list = field(default_factory=list)
    drivetime:  list = field(default_factory=list)
    teatime:    list = field(default_factory=list)

    def get(self, draw_type: DrawType) -> list:
        return getattr(self, draw_type.value)


# ===========================================================================
# HTTP session
# ===========================================================================

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
})


# ===========================================================================
# Parsers
# ===========================================================================

def _fetch(url: str, timeout: int = 15) -> Optional[BeautifulSoup]:
    """Fetch a URL and return parsed HTML, or None on error."""
    try:
        resp = SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        print(f"    [warn] {url} — {exc}")
        return None


def _extract_nums(tags) -> list:
    """Pull valid lottery integers (1-49) from a list of BS4 tags."""
    nums = []
    for tag in tags:
        txt = tag.get_text(strip=True)
        if txt.isdigit() and 1 <= int(txt) <= 49:
            nums.append(int(txt))
    return nums


def _parse_lottonumbers(soup: BeautifulSoup, draw_type: DrawType, limit: int) -> list:
    """uk.lottonumbers.com: <div class='result'> with date heading + ball <li> tags."""
    results = []
    blocks  = soup.select("div.result, article.result")
    for block in blocks[:limit]:
        date_tag  = block.find(["h2", "h3", "h4", "time"])
        date_str  = date_tag.get_text(strip=True) if date_tag else "Unknown"
        ball_tags = block.select("ul.numbers li, ol.numbers li, li.ball, li.number")
        if not ball_tags:
            ball_tags = block.find_all("li")
        nums = _extract_nums(ball_tags)
        if len(nums) < 6:
            continue
        results.append(DrawResult(
            draw_type  = draw_type,
            date       = date_str,
            numbers    = sorted(nums[:6]),
            bonus_ball = nums[6] if len(nums) >= 7 else None,
        ))
    return results


def _parse_national_lottery(soup: BeautifulSoup, draw_type: DrawType, limit: int) -> list:
    """za.national-lottery.com: table rows with date cell + number cells."""
    results  = []
    date_pat = re.compile(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+\d{1,2}[a-z]*\s+\w+\s*,?\s*\d{4}",
        re.IGNORECASE,
    )
    for row in soup.find_all("tr"):
        cells    = row.find_all(["td", "th"])
        row_text = " ".join(c.get_text(strip=True) for c in cells)
        m        = date_pat.search(row_text)
        if not m:
            continue
        nums = _extract_nums(cells)
        if len(nums) < 6:
            continue
        results.append(DrawResult(
            draw_type  = draw_type,
            date       = m.group(0).strip(),
            numbers    = sorted(nums[:6]),
            bonus_ball = nums[6] if len(nums) >= 7 else None,
        ))
        if len(results) >= limit:
            break
    return results


def _parse_text_fallback(soup: BeautifulSoup, draw_type: DrawType, limit: int) -> list:
    """Last-resort: scan plain text for date line + consecutive ball numbers."""
    results  = []
    date_pat = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s+\d{4}",
        re.IGNORECASE,
    )
    lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
    i = 0
    while i < len(lines) and len(results) < limit:
        if date_pat.search(lines[i]):
            date_str = lines[i]
            nums, j  = [], i + 1
            while j < len(lines) and len(nums) < 7:
                if re.fullmatch(r"\d{1,2}", lines[j]) and 1 <= int(lines[j]) <= 49:
                    nums.append(int(lines[j]))
                elif nums:
                    break
                j += 1
            if len(nums) >= 6:
                results.append(DrawResult(
                    draw_type  = draw_type,
                    date       = date_str,
                    numbers    = sorted(nums[:6]),
                    bonus_ball = nums[6] if len(nums) == 7 else None,
                ))
            i = j
        else:
            i += 1
    return results


def _make_sources(draw_type: DrawType) -> list:
    slug = draw_type.value
    return [
        {
            "name":   "uk.lottonumbers.com",
            "url":    f"https://uk.lottonumbers.com/uk49s-{slug}/results",
            "parser": _parse_lottonumbers,
        },
        {
            "name":   "za.national-lottery.com",
            "url":    f"https://za.national-lottery.com/uk-49s/results/{slug}",
            "parser": _parse_national_lottery,
        },
        {
            "name":   "za.lottonumbers.com",
            "url":    f"https://za.lottonumbers.com/uk-49s-{slug}/results",
            "parser": _parse_lottonumbers,
        },
        {
            "name":   "49sresult.com",
            "url":    f"https://49sresult.com/{slug}-results/",
            "parser": _parse_text_fallback,
        },
    ]


# ===========================================================================
# Public scraping API
# ===========================================================================

def get_draw_results(draw_type: DrawType, num_draws: int = 10) -> list:
    """
    Fetch the last N results for a single draw type.

    Args:
        draw_type: DrawType.BRUNCHTIME / LUNCHTIME / DRIVETIME / TEATIME
        num_draws: Number of recent draws to return (default 10).

    Returns:
        List of DrawResult objects, most recent first.

    Raises:
        RuntimeError: If all sources fail.
    """
    label = DRAW_LABELS[draw_type]
    print(f"\n[{label}]")
    for source in _make_sources(draw_type):
        print(f"  Trying {source['name']} ...", end=" ", flush=True)
        soup = _fetch(source["url"])
        if soup is None:
            continue
        results = source["parser"](soup, draw_type, num_draws)
        if results:
            print(f"OK — {len(results)} draw(s)")
            return results[:num_draws]
        print("no results parsed")
    raise RuntimeError(
        f"All sources failed for {draw_type.value}. "
        "Sites may be blocking automated requests. "
        "Consider a Selenium/Playwright headless browser approach."
    )


def get_all_draws(num_draws: int = 10) -> AllDrawResults:
    """
    Fetch the last N results for ALL four UK 49s draw types.

    Returns:
        AllDrawResults with .brunchtime / .lunchtime / .drivetime / .teatime lists.
        Failed draw types return an empty list (error printed, not raised).
    """
    container = AllDrawResults()
    for draw_type in DrawType:
        try:
            draws = get_draw_results(draw_type, num_draws)
            setattr(container, draw_type.value, draws)
        except RuntimeError as exc:
            print(f"  [error] {exc}")
    return container


# ===========================================================================
# Display helpers
# ===========================================================================

def display_draw(draw_type: DrawType, results: list) -> None:
    label = DRAW_LABELS[draw_type]
    bar   = "=" * 60
    print(f"\n{bar}")
    print(f"  UK 49s {label} — Last {len(results)} Draw(s)")
    print(f"{bar}")
    if not results:
        print("  No results available.")
        return
    for i, r in enumerate(results, 1):
        print(f"\n  {i:>2}. {r}")
    print()


def display_all(all_results: AllDrawResults) -> None:
    for draw_type in DrawType:
        display_draw(draw_type, all_results.get(draw_type))


# ===========================================================================
# Analyser
# ===========================================================================

COLOR_RANGES = {
    "Red":    range(1,  8),
    "Orange": range(8,  15),
    "Yellow": range(15, 22),
    "Green":  range(22, 29),
    "Blue":   range(29, 37),
    "Brown":  range(37, 43),
    "Purple": range(43, 50),
}

def _colour_of(n: int) -> str:
    for colour, rng in COLOR_RANGES.items():
        if n in rng:
            return colour
    return "Unknown"


def _clamp(n: int, lo: int = 1, hi: int = 49) -> Optional[int]:
    """Return n if in valid lottery range, else None."""
    return n if lo <= n <= hi else None


def _concat(a: int, b: int) -> int:
    """Concatenate two ints as digit strings: _concat(12, 3) -> 123."""
    return int(f"{a}{b}")


def _build_sets(numbers: list, bonus: int) -> dict:
    """
    Compute intermediate values x1-x9 and candidate sets S1, S2, S3, S5.

    Args:
        numbers: 6 main draw balls (ints).
        bonus:   Bonus/booster ball (int).

    Returns:
        Dict with keys 'x' (intermediates), 'S1', 'S2', 'S3', 'S5'.
    """
    r1, r2, r3, r4, r5, r6 = numbers
    r7 = bonus

    x_sum6 = r1 + r2 + r3 + r4 + r5 + r6
    x_sum7 = x_sum6 + r7

    x1, x2, x3 = x_sum6, x_sum6, x_sum6
    x4, x5, x6 = x_sum7, x_sum7, x_sum7
    x7 = x1 + x2 + x3        # 3 * x_sum6
    x8 = x4 + x5 + x6        # 3 * x_sum7
    x9 = x7 + x8             # 3 * (x_sum6 + x_sum7)

    # Set 1 — concatenation / addition combos
    s1_candidates = [
        _concat(x4, x5),
        _concat(x4, x5) + x6,
        _concat(x4, x6),
        _concat(x4, x5) + x8,
        _concat(x7, x8),
        _concat(x7, x9),
        _concat(x7, x8) + x9,
        _concat(x4, x4) + _concat(x7, x8),
    ]
    S1 = [n for n in s1_candidates if _clamp(n) is not None]

    # Set 2 — neighbour shifts for x4-x9
    S2 = []
    for val in [x4, x5, x6, x7, x8, x9]:
        if 20 <= val <= 29:
            c = _clamp(val + 10)
            if c: S2.append(c)
        elif 30 <= val <= 39:
            for adj in [val + 10, val - 10]:
                c = _clamp(adj)
                if c: S2.append(c)
        elif 40 <= val <= 49:
            c = _clamp(val - 10)
            if c: S2.append(c)
        else:
            c = _clamp(val)
            if c: S2.append(c)

    # Set 3 — today's date neighbourhood
    day = datetime.now().day
    S3  = [n for n in [day - 2, day - 1, day, day + 1, day + 2] if _clamp(n) is not None]

    # Set 5 — x1-x3 concatenation combos
    s5_candidates = [
        _concat(x1, x2),
        _concat(x1, x2) + x3,
        _concat(x1, x3),
    ]
    S5 = [n for n in s5_candidates if _clamp(n) is not None]

    return {
        "x":  dict(x1=x1, x2=x2, x3=x3, x4=x4, x5=x5, x6=x6, x7=x7, x8=x8, x9=x9),
        "S1": S1,
        "S2": S2,
        "S3": S3,
        "S5": S5,
    }


def _print_analysis(sets: dict, S4: list, draw_label: str = "") -> None:
    """Render the full analysis report to stdout."""
    S1, S2, S3, S5 = sets["S1"], sets["S2"], sets["S3"], sets["S5"]

    bar  = "=" * 60
    dash = "-" * 60
    print(f"\n{bar}")
    if draw_label:
        print(f"  ANALYSIS — {draw_label}")
    print(f"{bar}")

    # Intermediate values
    print("\n  Intermediate values (x1-x9):")
    for k, v in sets["x"].items():
        print(f"    {k} = {v}")

    # Sets summary
    def _fmt(label, lst):
        items = ", ".join(str(n) for n in lst) if lst else "(none in range 1-49)"
        print(f"\n  {label}: {items}")

    _fmt("Set 1 — concat/add combos          (S1)", S1)
    _fmt("Set 2 — neighbour shifts            (S2)", S2)
    _fmt("Set 3 — date neighbourhood          (S3)", S3)
    _fmt("Set 4 — TSE digits                  (S4)", S4)
    _fmt("Set 5 — x1-x3 combos               (S5)", S5)

    all_sets   = [S1, S2, S3, S4, S5]
    set_labels = ["S1", "S2", "S3", "S4", "S5"]

    # Build flat tagged list: (number, set_label)
    tagged = []
    for lbl, s in zip(set_labels, all_sets):
        for n in s:
            tagged.append((n, lbl))

    # --- By colour ---
    print(f"\n{dash}")
    print("  BY COLOUR  (groups with 3+ numbers)")
    print(f"{dash}")
    colour_groups: dict = {}
    for n, lbl in tagged:
        colour_groups.setdefault(_colour_of(n), []).append((n, lbl))

    found = False
    for colour in ["Red", "Orange", "Yellow", "Green", "Blue", "Brown", "Purple"]:
        items = colour_groups.get(colour, [])
        if len(items) >= 3:
            found = True
            display  = ", ".join(f"{n}({l})" for n, l in items)
            nums_int = [n for n, _ in items]
            combos   = list(itertools.combinations(nums_int, 3))
            print(f"\n  {colour}:  {display}")
            print(f"  3-ball combos ({len(combos)}):")
            for combo in combos:
                print(f"    {combo}")
    if not found:
        print("  (No colour group has 3+ numbers)")

    # --- By ending digit ---
    print(f"\n{dash}")
    print("  BY ENDING DIGIT  (groups with 3+ numbers)")
    print(f"{dash}")
    digit_groups: dict = {}
    for n, lbl in tagged:
        digit_groups.setdefault(n % 10, []).append((n, lbl))

    found = False
    for digit in sorted(digit_groups.keys()):
        items = digit_groups[digit]
        if len(items) >= 3:
            found = True
            display  = ", ".join(f"{n}({l})" for n, l in items)
            nums_int = [n for n, _ in items]
            combos   = list(itertools.combinations(nums_int, 3))
            print(f"\n  Ending in {digit}:  {display}")
            print(f"  3-ball combos ({len(combos)}):")
            for combo in combos:
                print(f"    {combo}")
    if not found:
        print("  (No ending-digit group has 3+ numbers)")

    print(f"\n{bar}\n")


def analyse(
    numbers: list,
    bonus_ball: int,
    tse: Optional[str] = None,
    draw_label: str = "",
) -> None:
    """
    Run prediction analysis on a draw result.

    Args:
        numbers:    List of exactly 6 main draw numbers (ints, 1-49).
        bonus_ball: Bonus/booster ball number (int, 1-49).
        tse:        2-character TSE string (e.g. "27").
                    If None, the sum of all 7 balls is used automatically.
        draw_label: Optional string shown in the report header.
    """
    if len(numbers) != 6:
        raise ValueError(f"Expected 6 numbers, got {len(numbers)}")

    sets = _build_sets(list(numbers), bonus_ball)

    # Set 4 from TSE
    if tse is None:
        tse_val = str(sets["x"]["x4"])   # default: sum of 7 balls
    else:
        tse_val = str(tse).strip()

    d1 = int(tse_val[0]) if len(tse_val) > 0 and tse_val[0].isdigit() else 0
    d2 = int(tse_val[1]) if len(tse_val) > 1 and tse_val[1].isdigit() else 0
    S4 = [n for n in [d1, d2, d1 + d2] if 1 <= n <= 49]

    sets["S4"] = S4
    _print_analysis(sets, S4, draw_label)


def analyse_manual() -> None:
    """Prompt the user for r1-r7 + TSE, then run analysis."""
    print("\n" + "=" * 60)
    print("  UK 49s Analyser — Manual Input")
    print("=" * 60)
    print("  Enter the previous draw result.\n")

    numbers = []
    for i in range(1, 7):
        while True:
            try:
                val = int(input(f"  r{i} (main ball {i}): ").strip())
                if 1 <= val <= 49:
                    numbers.append(val)
                    break
                print("  Must be 1-49.")
            except ValueError:
                print("  Please enter a whole number.")

    while True:
        try:
            bonus = int(input("  r7 (bonus ball): ").strip())
            if 1 <= bonus <= 49:
                break
            print("  Must be 1-49.")
        except ValueError:
            print("  Please enter a whole number.")

    tse = input(
        "  TSE (2-digit string, e.g. '27') — press Enter to auto-calculate: "
    ).strip() or None

    analyse(numbers, bonus, tse, draw_label="Manual Input")


def analyse_from_result(result: DrawResult, tse: Optional[str] = None) -> None:
    """
    Run analysis directly from a fetched DrawResult object.

    Args:
        result: A DrawResult from get_draw_results().
        tse:    Optional TSE string. Auto-calculated if omitted.
    """
    if result.bonus_ball is None:
        print(f"  [warn] No bonus ball for {result.date}, skipping analysis.")
        return
    label = f"{DRAW_LABELS[result.draw_type]} — {result.date}"
    analyse(result.numbers, result.bonus_ball, tse, draw_label=label)


# ===========================================================================
# CLI
# ===========================================================================

def _parse_args():
    parser = argparse.ArgumentParser(
        description="UK 49s Results Scraper + Draw Analyser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python uk49s_results.py                        # fetch all draws\n"
            "  python uk49s_results.py --draw lunch           # lunchtime only\n"
            "  python uk49s_results.py --analyse              # all draws + analyse latest\n"
            "  python uk49s_results.py --draw tea --analyse   # teatime + analyse\n"
            "  python uk49s_results.py --manual               # manual input, no fetch\n"
        ),
    )
    parser.add_argument(
        "--draw", "-d",
        choices=["brunch", "lunch", "drive", "tea", "all"],
        default="all",
        help="Which draw to fetch (default: all)",
    )
    parser.add_argument(
        "--num", "-n",
        type=int,
        default=10,
        help="Number of recent draws to show per type (default: 10)",
    )
    parser.add_argument(
        "--analyse", "-a",
        action="store_true",
        help="Run prediction analysis on the most recent fetched draw result",
    )
    parser.add_argument(
        "--tse",
        type=str,
        default=None,
        help="TSE value (2-digit string) for the analyser. Auto-calculated if omitted.",
    )
    parser.add_argument(
        "--manual", "-m",
        action="store_true",
        help="Skip fetching; run the analyser with manually entered numbers",
    )
    return parser.parse_args()


_DRAW_MAP = {
    "brunch": DrawType.BRUNCHTIME,
    "lunch":  DrawType.LUNCHTIME,
    "drive":  DrawType.DRIVETIME,
    "tea":    DrawType.TEATIME,
}

if __name__ == "__main__":
    args = _parse_args()

    if args.manual:
        analyse_manual()
        sys.exit(0)

    if args.draw == "all":
        all_results = get_all_draws(num_draws=args.num)
        display_all(all_results)
        if args.analyse:
            print("\n" + "=" * 60)
            print("  Running analysis on the most recent result of each draw")
            print("=" * 60)
            for draw_type in DrawType:
                draws = all_results.get(draw_type)
                if draws:
                    analyse_from_result(draws[0], tse=args.tse)
    else:
        dt      = _DRAW_MAP[args.draw]
        results = get_draw_results(dt, num_draws=args.num)
        display_draw(dt, results)
        if args.analyse and results:
            analyse_from_result(results[0], tse=args.tse)
