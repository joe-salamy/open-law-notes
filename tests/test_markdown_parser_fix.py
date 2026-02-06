"""Test the markdown parser fix for bold and italic nesting."""

from src.markdown_parser import parse_inline_styles, parse_line

# Test case 1: The problematic pattern from the user's file
test_text = '**_Case Example: Dementas v. Estate of Tallas_ (Referred to as "DeSantis" v. McWilliams/Upper Deck in lecture)**'

print("Testing: " + test_text)
print()

plain_text, styles = parse_inline_styles(test_text)

print(f"Plain text: {plain_text}")
print(f"Number of styles: {len(styles)}")
print()

for i, style in enumerate(styles):
    styled_portion = plain_text[style.start : style.end]
    print(f"Style {i+1}:")
    print(f"  Range: {style.start}-{style.end}")
    print(f"  Text: '{styled_portion}'")
    print(f"  Bold: {style.bold}, Italic: {style.italic}")
    print()

# Expected output:
# - "Case Example: Dementas v. Estate of Tallas" should be both bold and italic
# - "(Referred to as \"DeSantis\" v. McWilliams/Upper Deck in lecture)" should be bold only

print("=" * 80)
print("Expected results:")
print("- 'Case Example: Dementas v. Estate of Tallas' should be bold=True, italic=True")
print(
    "- '(Referred to as \"DeSantis\" v. McWilliams/Upper Deck in lecture)' should be bold=True, italic=False"
)
print()

# Test case 2: The full line as a list item
print("=" * 80)
print("\nTesting full line as list item:")
test_line = '- **_Case Example: Dementas v. Estate of Tallas_ (Referred to as "DeSantis" v. McWilliams/Upper Deck in lecture)**'

parsed = parse_line(test_line)
print(f"Line type: {parsed.line_type}")
print(f"Plain text: {parsed.plain_text}")
print(f"Number of styles: {len(parsed.styles)}")
print()

for i, style in enumerate(parsed.styles):
    styled_portion = parsed.plain_text[style.start : style.end]
    print(f"Style {i+1}:")
    print(f"  Range: {style.start}-{style.end}")
    print(f"  Text: '{styled_portion}'")
    print(f"  Bold: {style.bold}, Italic: {style.italic}")
    print()
