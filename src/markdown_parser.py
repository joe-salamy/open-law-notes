"""
Markdown to Google Docs API request parser.
Converts markdown content to Google Docs batchUpdate requests using only the native API.
"""

import re
import subprocess
import platform
from dataclasses import dataclass, field
from typing import Optional
from .logger_config import get_logger

logger = get_logger(__name__)


@dataclass
class StyleRange:
    """Represents a text style to apply over a range."""

    start: int
    end: int
    bold: bool = False
    italic: bool = False


@dataclass
class ParsedLine:
    """Represents a parsed markdown line with its content and metadata."""

    plain_text: str
    line_type: str  # 'header', 'paragraph', 'ul', 'ol', 'hr', 'blockquote', 'table_row', 'empty'
    header_level: int = 0
    list_nesting: int = 0
    styles: list[StyleRange] = field(default_factory=list)


class IndexTracker:
    """Tracks document indices as content is inserted."""

    def __init__(self, start_index: int):
        self.current_index = start_index

    def advance(self, length: int):
        """Advance the index by the given length."""
        self.current_index += length

    def get_range(self, local_start: int, local_end: int) -> tuple[int, int]:
        """Get absolute document indices for a local range within current text."""
        return (self.current_index + local_start, self.current_index + local_end)


# =============================================================================
# Inline Style Parsing
# =============================================================================


def parse_inline_styles(text: str) -> tuple[str, list[StyleRange]]:
    """
    Parse inline markdown styles (bold, italic) and return plain text with style ranges.

    Handles:
    - **bold** or __bold__
    - *italic* or _italic_ (but not underscores in words)
    - ***bold italic*** or ___bold italic___
    - **_bold italic_** or _**bold italic**_

    Args:
        text: Markdown text with inline formatting

    Returns:
        Tuple of (plain_text, list of StyleRange objects)
    """
    styles = []
    result_text = text

    # Process in order: bold+italic first, then bold, then italic
    # This ensures we handle combined styles correctly

    # Pattern for bold+italic: ***text*** or ___text___
    result_text, styles = _extract_bold_italic(result_text, styles)

    # Pattern for **_text_** or _**text**_ combinations
    result_text, styles = _extract_mixed_bold_italic(result_text, styles)

    # Pattern for bold: **text** or __text__
    result_text, styles = _extract_bold(result_text, styles)

    # Pattern for italic: *text* or _text_ (avoiding underscores in words)
    result_text, styles = _extract_italic(result_text, styles)

    return result_text, styles


def _extract_bold_italic(
    text: str, styles: list[StyleRange]
) -> tuple[str, list[StyleRange]]:
    """Extract ***bold italic*** patterns."""
    pattern = r"\*\*\*([^*]+)\*\*\*|___([^_]+)___"

    while True:
        match = re.search(pattern, text)
        if not match:
            break

        content = match.group(1) or match.group(2)
        start = match.start()

        # Replace the markdown with plain text
        text = text[: match.start()] + content + text[match.end() :]

        # Add style range
        styles.append(
            StyleRange(start=start, end=start + len(content), bold=True, italic=True)
        )

    return text, styles


def _extract_mixed_bold_italic(
    text: str, styles: list[StyleRange]
) -> tuple[str, list[StyleRange]]:
    """Extract **_text_** or _**text**_ patterns, including nested cases like **_text_ more**."""

    # Handle nesting case 1: **_italic text_ remaining bold text**
    # This pattern captures bold wrapping partial italic
    pattern_nested_bold_outer = r"\*\*_([^_]+)_([^*]*)\*\*"

    while True:
        match = re.search(pattern_nested_bold_outer, text)
        if not match:
            break

        italic_content = match.group(1)  # The italic part
        remaining_content = match.group(2)  # The remaining bold-only part
        start = match.start()

        # Reconstruct without markdown markers
        full_content = italic_content + remaining_content
        text = text[: match.start()] + full_content + text[match.end() :]

        # Add italic style for the first part
        styles.append(
            StyleRange(
                start=start, end=start + len(italic_content), bold=True, italic=True
            )
        )

        # Add bold-only style for the remaining part (if any)
        if remaining_content:
            styles.append(
                StyleRange(
                    start=start + len(italic_content),
                    end=start + len(full_content),
                    bold=True,
                    italic=False,
                )
            )

    # Handle nesting case 2: _**bold text** remaining italic text_
    # This pattern captures italic wrapping partial bold
    pattern_nested_italic_outer = r"_\*\*([^*]+)\*\*([^_]*)_"

    while True:
        match = re.search(pattern_nested_italic_outer, text)
        if not match:
            break

        bold_content = match.group(1)  # The bold part
        remaining_content = match.group(2)  # The remaining italic-only part
        start = match.start()

        # Reconstruct without markdown markers
        full_content = bold_content + remaining_content
        text = text[: match.start()] + full_content + text[match.end() :]

        # Add bold style for the first part
        styles.append(
            StyleRange(
                start=start, end=start + len(bold_content), bold=True, italic=True
            )
        )

        # Add italic-only style for the remaining part (if any)
        if remaining_content:
            styles.append(
                StyleRange(
                    start=start + len(bold_content),
                    end=start + len(full_content),
                    bold=False,
                    italic=True,
                )
            )

    # Now handle the symmetric cases where bold and italic have same boundaries
    patterns = [
        r"\*\*_([^_]+)_\*\*",  # **_text_**
        r"_\*\*([^*]+)\*\*_",  # _**text**_
        r"\*\*\s*_([^_]+)_\s*\*\*",  # ** _text_ **
    ]

    for pattern in patterns:
        while True:
            match = re.search(pattern, text)
            if not match:
                break

            content = match.group(1)
            start = match.start()

            text = text[: match.start()] + content + text[match.end() :]

            styles.append(
                StyleRange(
                    start=start, end=start + len(content), bold=True, italic=True
                )
            )

    return text, styles


def _extract_bold(text: str, styles: list[StyleRange]) -> tuple[str, list[StyleRange]]:
    """Extract **bold** or __bold__ patterns."""
    pattern = r"\*\*([^*]+)\*\*|__([^_]+)__"

    while True:
        match = re.search(pattern, text)
        if not match:
            break

        content = match.group(1) or match.group(2)
        start = match.start()

        text = text[: match.start()] + content + text[match.end() :]

        # Check if this range overlaps with existing styles
        overlapping = False
        for style in styles:
            if (
                style.start <= start < style.end
                or style.start < start + len(content) <= style.end
            ):
                overlapping = True
                break

        if not overlapping:
            styles.append(
                StyleRange(
                    start=start, end=start + len(content), bold=True, italic=False
                )
            )

    return text, styles


def _extract_italic(
    text: str, styles: list[StyleRange]
) -> tuple[str, list[StyleRange]]:
    """Extract *italic* or _italic_ patterns (avoiding underscores in words)."""
    # For asterisk italic: *text*
    pattern_asterisk = r"(?<!\*)\*([^*]+)\*(?!\*)"

    while True:
        match = re.search(pattern_asterisk, text)
        if not match:
            break

        content = match.group(1)
        start = match.start()

        text = text[: match.start()] + content + text[match.end() :]

        # Check for overlapping styles
        overlapping = False
        for style in styles:
            if (
                style.start <= start < style.end
                or style.start < start + len(content) <= style.end
            ):
                overlapping = True
                break

        if not overlapping:
            styles.append(
                StyleRange(
                    start=start, end=start + len(content), bold=False, italic=True
                )
            )

    # For underscore italic: _text_ (not inside words)
    # Look for underscores preceded by space/start and followed by space/end
    pattern_underscore = r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])"

    while True:
        match = re.search(pattern_underscore, text)
        if not match:
            break

        content = match.group(1)
        start = match.start()

        text = text[: match.start()] + content + text[match.end() :]

        overlapping = False
        for style in styles:
            if (
                style.start <= start < style.end
                or style.start < start + len(content) <= style.end
            ):
                overlapping = True
                break

        if not overlapping:
            styles.append(
                StyleRange(
                    start=start, end=start + len(content), bold=False, italic=True
                )
            )

    return text, styles


# =============================================================================
# Line Parsing
# =============================================================================


def parse_line(line: str) -> ParsedLine:
    """
    Parse a single markdown line and determine its type and content.

    Args:
        line: A single line of markdown text

    Returns:
        ParsedLine object with parsed information
    """
    # Empty line
    if not line.strip():
        return ParsedLine(plain_text="", line_type="empty")

    # Horizontal rule: ---, ***, ___
    if re.match(r"^[\-\*_]{3,}\s*$", line.strip()):
        return ParsedLine(plain_text="", line_type="hr")

    # Headers: # to ######
    header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if header_match:
        level = len(header_match.group(1))
        content = header_match.group(2)
        plain_text, styles = parse_inline_styles(content)
        return ParsedLine(
            plain_text=plain_text, line_type="header", header_level=level, styles=styles
        )

    # Blockquote: > text
    blockquote_match = re.match(r"^>\s*(.*)$", line)
    if blockquote_match:
        content = blockquote_match.group(1)
        plain_text, styles = parse_inline_styles(content)
        return ParsedLine(plain_text=plain_text, line_type="blockquote", styles=styles)

    # Unordered list with indentation detection
    ul_match = re.match(r"^(\s*)([\*\-\+])\s+(.+)$", line)
    if ul_match:
        indent = len(ul_match.group(1))
        content = ul_match.group(3)
        # Calculate nesting level (2 spaces = 1 level typically)
        nesting = indent // 2
        plain_text, styles = parse_inline_styles(content)
        return ParsedLine(
            plain_text=plain_text, line_type="ul", list_nesting=nesting, styles=styles
        )

    # Ordered list with indentation detection
    ol_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
    if ol_match:
        indent = len(ol_match.group(1))
        content = ol_match.group(3)
        nesting = indent // 2
        plain_text, styles = parse_inline_styles(content)
        return ParsedLine(
            plain_text=plain_text, line_type="ol", list_nesting=nesting, styles=styles
        )

    # Table row: | col1 | col2 |
    if line.strip().startswith("|") and line.strip().endswith("|"):
        return ParsedLine(plain_text=line.strip(), line_type="table_row")

    # Default: paragraph
    plain_text, styles = parse_inline_styles(line)
    return ParsedLine(plain_text=plain_text, line_type="paragraph", styles=styles)


# =============================================================================
# Google Docs Request Builders
# =============================================================================


def build_insert_text_request(index: int, text: str) -> dict:
    """
    Build a Google Docs insertText request.

    Args:
        index: Document index where text should be inserted
        text: Text to insert

    Returns:
        Google Docs API request dict
    """
    return {"insertText": {"location": {"index": index}, "text": text}}


def build_text_style_request(
    start_index: int, end_index: int, bold: bool = False, italic: bool = False
) -> dict:
    """
    Build a Google Docs updateTextStyle request.

    Args:
        start_index: Start of the range to style
        end_index: End of the range to style
        bold: Whether to apply bold
        italic: Whether to apply italic

    Returns:
        Google Docs API request dict
    """
    text_style = {}
    fields = []

    if bold:
        text_style["bold"] = True
        fields.append("bold")

    if italic:
        text_style["italic"] = True
        fields.append("italic")

    return {
        "updateTextStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "textStyle": text_style,
            "fields": ",".join(fields),
        }
    }


def build_paragraph_style_request(
    start_index: int, end_index: int, named_style: str
) -> dict:
    """
    Build a Google Docs updateParagraphStyle request for headers.

    Args:
        start_index: Start of the paragraph range
        end_index: End of the paragraph range
        named_style: Named style type (e.g., 'HEADING_1', 'HEADING_2', 'NORMAL_TEXT')

    Returns:
        Google Docs API request dict
    """
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "paragraphStyle": {"namedStyleType": named_style},
            "fields": "namedStyleType",
        }
    }


def build_blockquote_style_request(start_index: int, end_index: int) -> dict:
    """
    Build a Google Docs updateParagraphStyle request for blockquotes.
    Uses indentation and optional styling to indicate a quote.

    Args:
        start_index: Start of the paragraph range
        end_index: End of the paragraph range

    Returns:
        Google Docs API request dict
    """
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "paragraphStyle": {
                "indentStart": {"magnitude": 36, "unit": "PT"},  # 0.5 inch indent
                "indentFirstLine": {"magnitude": 36, "unit": "PT"},
            },
            "fields": "indentStart,indentFirstLine",
        }
    }


def build_bullet_request(
    start_index: int, end_index: int, bullet_preset: str, nesting_level: int = 0
) -> dict:
    """
    Build a Google Docs createParagraphBullets request.

    Args:
        start_index: Start of the paragraph range
        end_index: End of the paragraph range
        bullet_preset: Preset type ('BULLET_DISC_CIRCLE_SQUARE' for unordered,
                      'NUMBERED_DECIMAL_ALPHA_ROMAN' for ordered)
        nesting_level: Nesting level for the bullet (0 = top level)

    Returns:
        Google Docs API request dict
    """
    return {
        "createParagraphBullets": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "bulletPreset": bullet_preset,
        }
    }


def build_update_bullet_nesting_request(
    start_index: int, end_index: int, nesting_level: int
) -> dict:
    """
    Build a request to update bullet nesting level via paragraph indentation.
    Google Docs handles nesting through indentation levels.

    Args:
        start_index: Start of the paragraph range
        end_index: End of the paragraph range
        nesting_level: Desired nesting level

    Returns:
        Google Docs API request dict
    """
    indent_magnitude = 36 * (nesting_level + 1)  # 36 PT per level

    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "paragraphStyle": {
                "indentStart": {"magnitude": indent_magnitude, "unit": "PT"},
                "indentFirstLine": {"magnitude": indent_magnitude, "unit": "PT"},
            },
            "fields": "indentStart,indentFirstLine",
        }
    }


def build_horizontal_rule_request(index: int) -> list[dict]:
    """
    Build requests for a horizontal rule.
    Google Docs doesn't have a native HR, so we use a paragraph with a bottom border.

    Args:
        index: Document index where the rule should be inserted

    Returns:
        List of Google Docs API request dicts
    """
    # Insert a blank line with a bottom border to simulate HR
    requests = [
        {"insertText": {"location": {"index": index}, "text": "\n"}},
        {
            "updateParagraphStyle": {
                "range": {"startIndex": index, "endIndex": index + 1},
                "paragraphStyle": {
                    "borderBottom": {
                        "color": {
                            "color": {
                                "rgbColor": {"red": 0.6, "green": 0.6, "blue": 0.6}
                            }
                        },
                        "width": {"magnitude": 1, "unit": "PT"},
                        "padding": {"magnitude": 6, "unit": "PT"},
                        "dashStyle": "SOLID",
                    }
                },
                "fields": "borderBottom",
            }
        },
    ]
    return requests


def build_table_request(index: int, rows: int, columns: int) -> dict:
    """
    Build a Google Docs insertTable request.

    Args:
        index: Document index where the table should be inserted
        rows: Number of rows
        columns: Number of columns

    Returns:
        Google Docs API request dict
    """
    return {
        "insertTable": {"rows": rows, "columns": columns, "location": {"index": index}}
    }


# =============================================================================
# Table Parsing
# =============================================================================


def parse_table_rows(lines: list[str], start_idx: int) -> tuple[list[list[str]], int]:
    """
    Parse consecutive table rows starting from start_idx.

    Args:
        lines: All lines of the document
        start_idx: Index of the first table row line

    Returns:
        Tuple of (list of rows where each row is a list of cell contents,
                  number of lines consumed)
    """
    rows = []
    i = start_idx

    while i < len(lines):
        line = lines[i].strip()

        # Check if still a table row
        if not (line.startswith("|") and line.endswith("|")):
            break

        # Skip separator rows (|---|---|)
        if re.match(r"^\|[\s\-:]+\|$", line.replace("|", "|").replace("-", "-")):
            # Check if it's a separator row
            cells = [c.strip() for c in line[1:-1].split("|")]
            if all(re.match(r"^:?-+:?$", c) or c == "" for c in cells):
                i += 1
                continue

        # Parse cell contents
        cells = [c.strip() for c in line[1:-1].split("|")]
        rows.append(cells)
        i += 1

    return rows, i - start_idx


# =============================================================================
# Main Parser
# =============================================================================


def parse_markdown_to_requests(
    markdown_content: str, start_index: int, debug: bool = False
) -> list[dict]:
    """
    Parse markdown content and generate Google Docs API requests.

    This is the main entry point for converting markdown to Google Docs format.
    Handles all supported markdown elements including inline formatting.

    Args:
        markdown_content: The markdown content to convert
        start_index: The document index at which to start inserting content
        debug: Whether to enable debug logging

    Returns:
        List of Google Docs API requests to be used in batchUpdate
    """
    # Format with Prettier first
    markdown_content = _format_with_prettier(markdown_content)

    requests = []
    tracker = IndexTracker(start_index)

    lines = markdown_content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        parsed = parse_line(line)

        if debug:
            logger.debug(
                f"Line {i}: type={parsed.line_type}, text='{parsed.plain_text[:50]}...' if len > 50"
            )

        # Handle empty lines
        if parsed.line_type == "empty":
            requests.append(build_insert_text_request(tracker.current_index, "\n"))
            tracker.advance(1)
            i += 1
            continue

        # Handle horizontal rules
        if parsed.line_type == "hr":
            hr_requests = build_horizontal_rule_request(tracker.current_index)
            requests.extend(hr_requests)
            tracker.advance(1)  # For the newline
            i += 1
            continue

        # Handle tables
        if parsed.line_type == "table_row":
            table_rows, lines_consumed = parse_table_rows(lines, i)
            if table_rows:
                table_requests = _generate_table_requests(
                    table_rows, tracker.current_index
                )
                requests.extend(table_requests)
                # Calculate how much space the table takes
                # Each cell content + table structure
                total_chars = (
                    sum(len(cell) + 1 for row in table_rows for cell in row)
                    + len(table_rows)
                    + 2
                )  # Approximate
                tracker.advance(total_chars)
            i += lines_consumed
            continue

        # Handle text-based elements (headers, paragraphs, lists, blockquotes)
        text_with_newline = parsed.plain_text + "\n"
        text_start = tracker.current_index
        text_end = text_start + len(text_with_newline)

        # Step 1: Insert the plain text
        requests.append(build_insert_text_request(text_start, text_with_newline))

        # Step 2: Apply inline styles (bold, italic)
        for style in parsed.styles:
            abs_start, abs_end = tracker.get_range(style.start, style.end)
            if style.bold or style.italic:
                requests.append(
                    build_text_style_request(
                        abs_start, abs_end, bold=style.bold, italic=style.italic
                    )
                )

        # Step 3: Apply block-level formatting
        if parsed.line_type == "header":
            style_name = f"HEADING_{parsed.header_level}"
            requests.append(
                build_paragraph_style_request(text_start, text_end, style_name)
            )

        elif parsed.line_type == "blockquote":
            requests.append(build_blockquote_style_request(text_start, text_end))
            # Also apply italic styling to blockquotes for visual distinction
            requests.append(
                build_text_style_request(
                    text_start, text_end - 1, italic=True  # -1 to exclude newline
                )
            )

        elif parsed.line_type == "ul":
            requests.append(
                build_bullet_request(
                    text_start,
                    text_end,
                    "BULLET_DISC_CIRCLE_SQUARE",
                    parsed.list_nesting,
                )
            )
            # Handle nesting
            if parsed.list_nesting > 0:
                requests.append(
                    build_update_bullet_nesting_request(
                        text_start, text_end, parsed.list_nesting
                    )
                )

        elif parsed.line_type == "ol":
            requests.append(
                build_bullet_request(
                    text_start,
                    text_end,
                    "NUMBERED_DECIMAL_ALPHA_ROMAN",
                    parsed.list_nesting,
                )
            )
            # Handle nesting
            if parsed.list_nesting > 0:
                requests.append(
                    build_update_bullet_nesting_request(
                        text_start, text_end, parsed.list_nesting
                    )
                )

        # Advance tracker
        tracker.advance(len(text_with_newline))
        i += 1

    if debug:
        logger.debug(f"Generated {len(requests)} requests from markdown")

    return requests


def _generate_table_requests(
    table_rows: list[list[str]], start_index: int
) -> list[dict]:
    """
    Generate requests to create and populate a table.

    Args:
        table_rows: List of rows, each row is a list of cell contents
        start_index: Document index where table should be inserted

    Returns:
        List of Google Docs API requests
    """
    if not table_rows:
        return []

    num_rows = len(table_rows)
    num_cols = max(len(row) for row in table_rows)

    requests = []

    # Insert the table structure
    requests.append(build_table_request(start_index, num_rows, num_cols))

    # Note: After inserting a table, we need to populate cells
    # The table insertion creates the structure, and cells are populated
    # by inserting text at specific indices within the table
    # This is complex as table cell indices need to be calculated
    # For now, we insert the table structure and content follows

    # After table insertion, indices shift. We need to insert cell content
    # Table structure: each cell can be accessed after the table is created
    # This is a simplified approach - full implementation would track cell indices

    current_index = start_index + 1  # After table start

    for row_idx, row in enumerate(table_rows):
        for col_idx, cell_content in enumerate(row):
            if cell_content:
                # Parse inline styles in cell content
                plain_text, styles = parse_inline_styles(cell_content)

                # Insert cell text (simplified - actual implementation needs
                # proper cell index calculation)
                requests.append(
                    {
                        "insertText": {
                            "location": {"index": current_index},
                            "text": plain_text,
                        }
                    }
                )

                # Apply styles to cell content
                for style in styles:
                    if style.bold or style.italic:
                        requests.append(
                            build_text_style_request(
                                current_index + style.start,
                                current_index + style.end,
                                bold=style.bold,
                                italic=style.italic,
                            )
                        )

                current_index += len(plain_text) + 1
            else:
                current_index += 1

        current_index += 1  # End of row

    return requests


def _format_with_prettier(markdown_content: str) -> str:
    """
    Format markdown content using Prettier CLI.

    Args:
        markdown_content: The markdown content to format

    Returns:
        Formatted markdown content, or original content if Prettier fails
    """
    prettier_cmd = "prettier.cmd" if platform.system() == "Windows" else "prettier"

    try:
        result = subprocess.run(
            [prettier_cmd, "--parser", "markdown"],
            input=markdown_content,
            text=True,
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.debug("Successfully formatted markdown with Prettier")
            return result.stdout
        else:
            logger.warning(
                f"Prettier formatting failed (exit code {result.returncode}): {result.stderr}"
            )
            return markdown_content

    except FileNotFoundError:
        logger.warning(
            "Prettier not found. Install with: npm install -g prettier. "
            "Continuing with unformatted markdown."
        )
        return markdown_content
    except subprocess.TimeoutExpired:
        logger.warning("Prettier formatting timed out. Using original markdown.")
        return markdown_content
    except Exception as e:
        logger.warning(f"Error running Prettier: {e}. Using original markdown.")
        return markdown_content
