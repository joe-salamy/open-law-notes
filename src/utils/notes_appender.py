"""
Append generated notes to consolidated markdown files.
Called inline after LLM processing completes, using only the files
that were just processed (no directory scanning).
"""

import re
from datetime import date, timedelta
from pathlib import Path

from .logger_config import get_logger

logger = get_logger(__name__)

# Day abbreviation to weekday number (Monday=0)
DAY_TO_WEEKDAY = {"Mon": 0, "Tue": 1, "Wed": 2, "Thur": 3, "Fri": 4}

# Reverse: weekday number to abbreviation
WEEKDAY_TO_DAY = {v: k for k, v in DAY_TO_WEEKDAY.items()}

# Month abbreviations for parsing
MONTH_ABBRS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
MONTH_NUM_TO_ABBR = {v: k for k, v in MONTH_ABBRS.items()}


def get_last_h3_number(filepath: Path) -> int:
    """Parse the last ### {number}. header from a file. Returns 0 if none found."""
    if not filepath.exists():
        return 0
    text = filepath.read_text(encoding="utf-8")
    matches = re.findall(r"^### (\d+)\\?\.", text, re.MULTILINE)
    if matches:
        return int(matches[-1])
    return 0


def get_last_lecture_date(filepath: Path) -> date | None:
    """Parse the last lecture date from ### {n}. {Day}, {Mon} {date} headers."""
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8")
    # Match: ### 27. Thur, Mar 19 - ... (with optional backslash-escaped dot)
    matches = re.findall(r"^### \d+\\?\. \w+, (\w+) (\d+)", text, re.MULTILINE)
    if not matches:
        return None
    month_str, day_str = matches[-1]
    month = MONTH_ABBRS.get(month_str)
    if month is None:
        return None
    # Assume current academic year
    today = date.today()
    # Try current year first; if the date is far in the future, use previous year
    try:
        d = date(today.year, month, int(day_str))
    except ValueError:
        return None
    # If the parsed date is more than 6 months in the future, it's probably last year
    if d > today + timedelta(days=180):
        d = date(today.year - 1, month, int(day_str))
    return d


def next_meeting_date(last_date: date, meeting_days: list[str]) -> date:
    """Find the next class meeting date after last_date."""
    meeting_weekdays = [DAY_TO_WEEKDAY[d] for d in meeting_days]
    current = last_date + timedelta(days=1)
    # Search up to 14 days ahead (should always find within a week)
    for _ in range(14):
        if current.weekday() in meeting_weekdays:
            return current
        current += timedelta(days=1)
    # Fallback: just return next day (shouldn't happen)
    return last_date + timedelta(days=1)


def format_date(d: date) -> str:
    """Format a date as 'Wed, Jan 14' with custom day abbreviations."""
    day_abbr = WEEKDAY_TO_DAY.get(d.weekday(), d.strftime("%a"))
    month_abbr = MONTH_NUM_TO_ABBR.get(d.month, d.strftime("%b"))
    return f"{day_abbr}, {month_abbr} {d.day}"


def replace_h3_header(content: str, new_header: str) -> str:
    """Replace the first ### header line in content with new_header."""
    return re.sub(
        r"^### .+$", f"### {new_header}", content, count=1, flags=re.MULTILINE
    )


def extract_topic_from_h3(content: str) -> str:
    """Extract the topic text from ### **Topic** header, stripping bold markers."""
    match = re.search(r"^### \*\*(.+?)\*\*", content, re.MULTILINE)
    if match:
        return match.group(1)
    # Fallback: just grab whatever is after ###
    match = re.search(r"^### (.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip("* ")
    return "Untitled"


def append_reading_notes(class_folder: Path, md_files: list[Path]) -> int:
    """
    Append the given reading note files to class_folder/reading-notes.md.
    Deletes each file after appending.  Returns the number of notes appended.
    """
    target_file = class_folder / "reading-notes.md"

    if not md_files:
        return 0

    count = 0
    for md_file in md_files:
        next_num = get_last_h3_number(target_file) + 1
        content = md_file.read_text(encoding="utf-8")
        filename_stem = md_file.stem
        new_header = f"{next_num}\\. {filename_stem}"
        content = replace_h3_header(content, new_header)

        # Append to consolidated file
        with open(target_file, "a", encoding="utf-8") as f:
            if target_file.stat().st_size > 0 if target_file.exists() else False:
                f.write("\n\n")
            f.write(content.rstrip() + "\n")

        logger.info(f"✓ Appended reading: {new_header}")
        count += 1

    return count


def append_lecture_notes(
    class_folder: Path, md_files: list[Path], meeting_days: list[str]
) -> int:
    """
    Append the given lecture note files to class_folder/lecture-notes.md.
    Deletes each file after appending.  Returns the number of notes appended.
    """
    target_file = class_folder / "lecture-notes.md"

    if not md_files:
        return 0

    count = 0
    for md_file in md_files:
        next_num = get_last_h3_number(target_file) + 1
        content = md_file.read_text(encoding="utf-8")
        topic = extract_topic_from_h3(content)

        # Calculate date
        last_date = get_last_lecture_date(target_file)
        if last_date and meeting_days:
            lecture_date = next_meeting_date(last_date, meeting_days)
            date_str = format_date(lecture_date)
            new_header = f"{next_num}\\. {date_str} - {topic}"
        else:
            # First entry or no meeting days configured — skip date
            new_header = f"{next_num}\\. {topic}"

        content = replace_h3_header(content, new_header)

        # Append to consolidated file
        with open(target_file, "a", encoding="utf-8") as f:
            if target_file.exists() and target_file.stat().st_size > 0:
                f.write("\n\n")
            f.write(content.rstrip() + "\n")

        logger.info(f"✓ Appended lecture: {new_header}")
        count += 1

    return count
