"""Test processing the actual Bussel 10.21.2025.md file that had the issue."""

from src.markdown_parser import parse_line

# Read the actual file
file_path = r"c:\Users\joesa\OneDrive\Documents\law-school-python\smart-law-notes\tests\markdown\Bussel 10.21.2025.md"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and test line 20 (0-indexed is line 19)
print("Testing the problematic line from Bussel 10.21.2025.md")
print("=" * 80)
print()

problematic_line_number = 20  # 1-indexed
problematic_line = lines[problematic_line_number - 1].rstrip("\n")

print(f"Line {problematic_line_number}:")
print(f"  Raw: {repr(problematic_line)}")
print()

parsed = parse_line(problematic_line)

print(f"Parsed:")
print(f"  Type: {parsed.line_type}")
print(f"  Plain text: {parsed.plain_text}")
print(f"  Number of styles: {len(parsed.styles)}")
print()

if parsed.styles:
    print("Styles applied:")
    for i, style in enumerate(parsed.styles, 1):
        styled_text = parsed.plain_text[style.start : style.end]
        formatting = []
        if style.bold:
            formatting.append("BOLD")
        if style.italic:
            formatting.append("ITALIC")

        print(f"  Style {i}:")
        print(f"    Range: characters {style.start}-{style.end}")
        print(f"    Text: '{styled_text}'")
        print(f"    Formatting: {' + '.join(formatting)}")
        print()

print("=" * 80)
print("Expected results:")
print("  1. 'Case Example: Dementas v. Estate of Tallas' → BOLD + ITALIC")
print(
    "  2. '(Referred to as \"DeSantis\" v. McWilliams/Upper Deck in lecture)' → BOLD only"
)
print()

# Verify the results
if len(parsed.styles) == 2:
    style1 = parsed.styles[0]
    style2 = parsed.styles[1]

    text1 = parsed.plain_text[style1.start : style1.end]
    text2 = parsed.plain_text[style2.start : style2.end]

    if (
        style1.bold
        and style1.italic
        and "Case Example: Dementas v. Estate of Tallas" in text1
        and style2.bold
        and not style2.italic
    ):
        print("✓ SUCCESS: The markdown parser is now working correctly!")
    else:
        print("✗ ISSUE: Styles don't match expected formatting")
else:
    print(f"✗ ISSUE: Expected 2 styles but got {len(parsed.styles)}")
