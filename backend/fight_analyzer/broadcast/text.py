"""Reading scorebug text: fight clock, round number and fighter names.

OCR output is noisy in known ways (O for 0, l or I for 1, S for 5, a dropped
colon). Parsing accepts those only inside a clock-shaped token (m:ss with
seconds below 60) and rejects anything else instead of guessing.
"""

from __future__ import annotations

import re

_TO_DIGIT = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1", "|": "1", "i": "1",
                           "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2"})
_D = "[0-9OoDQIl|iSsBZz]"
_CLOCK = re.compile(rf"(?<![0-9A-Za-z:])({_D}{{1,2}})\s?[:;.]\s?({_D}{{2}})(?![0-9:])")
_BARE_CLOCK = re.compile(rf"^\s*({_D})({_D}{{2}})\s*$")  # colon not read: only inside the known clock area
_TENTHS = re.compile(r"^\s*(\d)\.(\d)\s*$")  # last seconds shown as 9.5
# the round indicator's pips after the number read as I / l / |
_ROUND = re.compile(r"(?<![A-Za-z0-9])(?:R(?:OUND|ND|D)?\s?([1-5lI])|([1-5])\s?(?:ST|ND|RD|TH))(?![A-HJ-KM-Za-hj-km-z0-9])",
                    re.IGNORECASE)
_BAR_BEFORE_R = re.compile(r"[|Il](?=R\s?[1-5])")
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
MAX_CLOCK_S = 600

# Words a scorebug shows in the name slots that are not names.
NOT_NAMES = frozenset("""
UFC PFL ONE BELLATOR RED BLUE BLACK WHITE GOLD GREEN GREY GRAY PURPLE ORANGE YELLOW PINK SILVER NAVY
TRUNK TRUNKS COLOR COLORS COLOUR COLOURS ROUND RD RND LIVE ODDS REPLAY SIGNIFICANT STRIKES STRIKE LANDED
TAKEDOWNS TAKEDOWN CONTROL TIME TOTAL CHAMPIONSHIP CHAMPION TITLE BOUT FIGHT MAIN EVENT VS TIMEX DRAFTKINGS
FLYWEIGHT BANTAMWEIGHT FEATHERWEIGHT LIGHTWEIGHT WELTERWEIGHT MIDDLEWEIGHT LIGHT HEAVYWEIGHT STRAWWEIGHT
WOMEN WOMENS INTERIM
""".split())


def parse_clock(text: str, bare: bool = False) -> float | None:
    """Seconds left on a clock read like '4:56' (first clock in the text). With
    `bare`, also '456' (colon not read) and '9.5' (tenths in the last seconds):
    only for text from the known clock area."""
    for m in _CLOCK.finditer(text):
        mm, ss = m.group(1).translate(_TO_DIGIT), m.group(2).translate(_TO_DIGIT)
        if mm.isdigit() and ss.isdigit() and int(ss) < 60 and int(mm) * 60 + int(ss) <= MAX_CLOCK_S:
            return float(int(mm) * 60 + int(ss))
    if bare:
        m = _BARE_CLOCK.match(text)
        if m:
            mm, ss = m.group(1).translate(_TO_DIGIT), m.group(2).translate(_TO_DIGIT)
            if mm.isdigit() and ss.isdigit() and int(ss) < 60:
                return float(int(mm) * 60 + int(ss))
        m = _TENTHS.match(text)
        if m:
            return int(m.group(1)) + int(m.group(2)) / 10
    return None


def parse_round(text: str) -> int | None:
    """Round number from 'R1', 'RD 2', 'ROUND 3', '2ND'... A bar drawn just before the
    R (read as '|', 'I' or 'l') is ignored."""
    for m in _ROUND.finditer(_BAR_BEFORE_R.sub(" ", text)):
        raw = (m.group(1) or m.group(2)).translate(_TO_DIGIT)
        if raw.isdigit() and 1 <= int(raw) <= 5:
            return int(raw)
    return None


def clean_name(text: str) -> str | None:
    """The name part of a scorebug name slot ('3 TOPURIA' -> 'TOPURIA'), or None."""
    words = [w for w in _WORD.findall(text) if len(w) >= 2 and w.upper() not in NOT_NAMES]
    name = " ".join(words)
    if sum(len(w) for w in words) < 3 or len(name) > 40:
        return None
    return name


def title_case(name: str) -> str:
    """'ILIA TOPURIA' -> 'Ilia Topuria', 'ST-PIERRE' -> 'St-Pierre', "O'MALLEY" -> "O'Malley".
    Python's str casing follows the Unicode default rules, independent of the
    locale: 'I' always lowers to 'i' (never the Turkish dotless 'ı')."""
    def part(p: str) -> str:
        return p[:1].upper() + p[1:].lower()
    return re.sub(r"[^\W\d_]+", lambda m: part(m.group(0)), name)
