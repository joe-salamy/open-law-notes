"""
One-time script to reconstruct individual output files from consolidated
lecture-notes.md and reading-notes.md documents.

Splits each file on ### h3 headers and saves each section as a separate
markdown file in the appropriate output folder.
"""

import re
import sys
from pathlib import Path

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import CLASSES, PARENT_FOLDER, LLM_BASE, LECTURE_OUTPUT, READING_OUTPUT


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove backslash-escaped dots (e.g. "27\." -> "27.")
    name = name.replace("\\.", ".")
    # Remove characters illegal in Windows filenames
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    # Truncate to reasonable length (short to avoid Windows path limit)
    if len(name) > 100:
        name = name[:100].strip()
    return name


def split_on_h3(text: str) -> list[tuple[str, str]]:
    """
    Split text on ### headers.
    Returns list of (header_text, full_section_content) tuples.
    """
    # Match ### at start of line, capture the rest of the line as header
    pattern = r'^(### .+)$'
    parts = re.split(pattern, text, flags=re.MULTILINE)

    sections = []
    # parts alternates: [before_first_header, header1, body1, header2, body2, ...]
    i = 1  # skip content before first header
    while i < len(parts) - 1:
        header_line = parts[i].strip()
        body = parts[i + 1]
        full_content = header_line + "\n" + body.strip()
        # Extract the header text after "### "
        header_text = header_line[4:]  # strip "### "
        sections.append((header_text, full_content))
        i += 2

    return sections


def extract_title_from_header(header_text: str) -> str:
    """
    Extract a filename-friendly title from the h3 header text.
    Headers look like:  "27\\. Thur, Mar 19 - Topic"  or  "5\\. Reading Title"
    Returns the part after the number prefix.
    """
    # Strip the leading number and escaped dot: "27\. " or "27. "
    match = re.match(r'\d+\\?\.\s*', header_text)
    if match:
        return header_text[match.end():]
    return header_text


def reconstruct(notes_file: Path, output_dir: Path, label: str) -> int:
    """Parse a consolidated notes file and save individual sections."""
    if not notes_file.exists():
        print(f"  {label}: {notes_file.name} not found, skipping")
        return 0

    text = notes_file.read_text(encoding="utf-8")
    sections = split_on_h3(text)

    if not sections:
        print(f"  {label}: no h3 sections found in {notes_file.name}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for header_text, content in sections:
        title = extract_title_from_header(header_text)
        filename = sanitize_filename(title) + ".md"
        out_path = output_dir / filename

        if out_path.exists():
            print(f"  {label}: SKIP (already exists) {filename}")
            continue

        out_path.write_text(content + "\n", encoding="utf-8")
        count += 1

    print(f"  {label}: {count} file(s) created in {output_dir}")
    return count


def main():
    total = 0
    for class_name in CLASSES:
        class_folder = Path(PARENT_FOLDER) / class_name
        print(f"\n{class_name}:")

        # Lecture notes
        lecture_notes = class_folder / "lecture-notes.md"
        lecture_output = class_folder / LLM_BASE / LECTURE_OUTPUT
        total += reconstruct(lecture_notes, lecture_output, "Lectures")

        # Reading notes
        reading_notes = class_folder / "reading-notes.md"
        reading_output = class_folder / LLM_BASE / READING_OUTPUT
        total += reconstruct(reading_notes, reading_output, "Readings")

    print(f"\nDone. {total} total file(s) reconstructed.")


if __name__ == "__main__":
    main()
