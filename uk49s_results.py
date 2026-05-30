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
    pip install -r requirements.txt
    playwright install chromium
"""

import re
import sys
import argparse
import itertools
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from dateutil import parser as date_parser


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
# Constants
# ===========================================================================

COLOUR_RANGES = {
    "Red":    range(1,  8),
    "Orange": range(8,  15),
    "Yellow": range(15, 22),
    "Green":  range(22, 29),
    "Blue":   range(29, 37),
    "Brown":  range(37, 43),
    "Purple": range(43, 50),
}


# ===========================================================================
# Playwright fetch (bypasses bot detection)
# ===========================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def _fetch_playwright(url: str, timeout: int = 30000) -> Optional[BeautifulSoup]:
    """
    Fetch URL using Playwright Chromium (bypasses most bot detection).
    Returns BeautifulSoup object or None.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox"
                ]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Add stealth: hide webdriver property
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Remove Playwright-specific properties
                delete navigator.__proto__.webdriver;
            """)
            
            page.goto(url, timeout=timeout, wait_until="networkidle")
            
            # Wait a little for dynamic content to load
            page.wait_for_timeout(2000)
            
            html = page.content()
            browser.close()
            return BeautifulSoup(html, "html.parser")
            
    except Exception as exc:
        print(f"    [warn] Playwright error on {url}: {exc}")
        return None


# ===========================================================================
# Parsers
# ===========================================================================

def _extract_nums(tags: list) -> list:
    """Extract all integers 1-49 from a list of BeautifulSoup tags/cells."""
    nums = []
    for tag in tags:
        text = tag.get_text(strip=True)
        # Extract all numbers from text (e.g. "Ball 27" -> 27)
        found = re.findall(r"\d+", text)
        for val_str in found:
            try:
                val = int(val_str)
                if 1 <= val <= 49:
                    nums.append(val)
            except ValueError:
                continue
    return nums


def _parse_date(date_str: str) -> str:
    """Parse and standardize date string."""
    try:
        parsed = date_parser.parse(date_str, fuzzy=True)
        return parsed.strftime("%A %d %B %Y")
    except:
        return date_str  # fallback to original


def _parse_lottonumbers(soup: BeautifulSoup, draw_type: DrawType, limit: int) -> list:
    """uk.lottonumbers.com: <div class='result'> or <div class='draw'> with date heading + ball <li> tags."""
    results = []
    blocks  = soup.select("div.result, article.result, div.draw")
    for block in blocks[:limit]:
        # Date often in strong or headers or just first div
        date_tag  = block.find(["h2", "h3", "h4", "time", "strong"])
        if not date_tag:
             date_container = block.find("div")
             if date_container:
                 date_tag = date_container

        date_str  = date_tag.get_text(strip=True) if date_tag else "Unknown"

        ball_tags = block.select("ul.numbers li, ol.numbers li, li.ball, li.number, .balls li")
        if not ball_tags:
            ball_tags = block.find_all("li")

        nums = _extract_nums(ball_tags)
        if len(nums) < 6:
            continue

        results.append(DrawResult(
            draw_type  = draw_type,
            date       = _parse_date(date_str),
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
            date       = _parse_date(m.group(0).strip()),
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
                    date       = _parse_date(date_str),
                    numbers    = sorted(nums[:6]),
                    bonus_ball = nums[6] if len(nums) == 7 else None,
                ))
            i = j
        else:
            i += 1
    return results


def _make_sources(draw_type: DrawType) -> list:
    slug = draw_type.value
    # Fix for lotteryextreme slugs
    extreme_slug = slug
    if slug == "brunchtime": extreme_slug = "brunch"
    if slug == "lunchtime":  extreme_slug = "lunch"
    if slug == "drivetime":  extreme_slug = "drive"
    if slug == "teatime":    extreme_slug = "tea"

    return [
        {
            "name":   "za.lottonumbers.com",
            "url":    f"https://za.lottonumbers.com/uk-49s-{slug}/results",
            "parser": _parse_lottonumbers,
        },
        {
            "name":   "www.lotteryextreme.com",
            "url":    f"https://www.lotteryextreme.com/49s-{extreme_slug}/results",
            "parser": _parse_lottonumbers,
        },
        {
            "name":   "www.49s.co.uk",
            "url":    f"https://49s.co.uk/49s/results/{slug}",
            "parser": _parse_national_lottery,
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
        soup = _fetch_playwright(source["url"])
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
        "Try updating Playwright: playwright install chromium"
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

def _colour_of(n: int) -> str:
    for colour, rng in COLOUR_RANGES.items():
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
    Compute variables v, w, x, y, z from balls r1-r7.

    Args:
        numbers: 6 main draw balls (ints).
        bonus:   Bonus/booster ball (int).

    Returns:
        Dict with key 'x' containing v, w, x, y, z.
    """
    r1, r2, r3, r4, r5, r6 = numbers
    r7 = bonus

    v = r1 + r2 + r3 + r4 + r5 + r6
    w = v + r7

    x = v * 3
    y = w * 3
    z = x + y

    return {
        "x": dict(v=v, w=w, x=x, y=y, z=z)
    }


def _print_analysis(sets: dict, draw_label: str = "") -> None:
    """Render the variables to stdout."""
    bar  = "=" * 60
    print(f"\n{bar}")
    if draw_label:
        print(f"  ANALYSIS — {draw_label}")
    print(f"{bar}")

    print("\n  Variables (v, w, x, y, z):")
    for k, val in sets["x"].items():
        print(f"    {k} = {val}")

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
        tse:        Not used.
        draw_label: Optional string shown in the report header.
    """
    if len(numbers) != 6:
        raise ValueError(f"Expected 6 numbers, got {len(numbers)}")

    sets = _build_sets(list(numbers), bonus_ball)
    _print_analysis(sets, draw_label)


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