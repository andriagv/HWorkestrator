"""Week numbers: 'VI', '6', 'კვირა 6', 'Week 6' -> 6, and matching against Moodle section names."""
import re

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman_to_int(s):
    s = s.upper()
    total = 0
    for i, c in enumerate(s):
        v = _ROMAN[c]
        total += -v if i + 1 < len(s) and _ROMAN[s[i + 1]] > v else v
    return total


def int_to_roman(n):
    out = ""
    for v, r in [(50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= v:
            out += r
            n -= v
    return out


def parse_week(text):
    """First number (arabic or roman) in the text, or None."""
    m = re.search(r"\d+", text)
    if m:
        return int(m.group())
    m = re.search(r"\b([IVXLivxl]{1,6})\b", text)
    if m:
        try:
            return roman_to_int(m.group(1))
        except KeyError:
            return None
    return None


def numbers_in(name):
    """All week-like numbers in a section name (arabic and standalone roman)."""
    nums = [int(x) for x in re.findall(r"\d+", name)]
    for tok in re.findall(r"(?<![A-Za-z])[IVXL]{1,6}(?![A-Za-z])", name):
        try:
            nums.append(roman_to_int(tok))
        except KeyError:
            pass
    return nums


def find_week_section(sections, week):
    """sections: Moodle core_course_get_contents list. Prefer a section whose NAME carries the week
    number together with the word კვირა/week; then any name with that number; then section index."""
    named = [s for s in sections if re.search(r"კვირ|week", s.get("name", ""), re.I)
             and week in numbers_in(s["name"])]
    if named:
        return named[0]
    loose = [s for s in sections if week in numbers_in(s.get("name", ""))]
    if loose:
        return loose[0]
    for s in sections:
        if s.get("section") == week:
            return s
    return None


def week_sections(sections):
    """[(week_number, section)] for sections that are weekly (name contains კვირა/week + a number)."""
    out = []
    for s in sections:
        if re.search(r"კვირ|week", s.get("name", ""), re.I):
            nums = numbers_in(s["name"])
            if nums:
                out.append((nums[0], s))
    return sorted(out, key=lambda x: x[0])
