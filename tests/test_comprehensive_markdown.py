"""Comprehensive test for bold and italic formatting in markdown parser."""

from src.markdown_parser import parse_inline_styles

test_cases = [
    # (input, expected_plain_text, expected_formatting_description)
    (
        "**_Case Example: Dementas v. Estate of Tallas_ (more text)**",
        "Case Example: Dementas v. Estate of Tallas (more text)",
        "First part bold+italic, second part bold-only",
    ),
    (
        "_**Bold text** and more italic_",
        "Bold text and more italic",
        "First part bold+italic, second part italic-only",
    ),
    ("**_Full text_**", "Full text", "Entire text bold+italic"),
    ("_**Full text**_", "Full text", "Entire text bold+italic"),
    ("**Just bold**", "Just bold", "Entire text bold"),
    ("_Just italic_", "Just italic", "Entire text italic"),
    ("*Also italic*", "Also italic", "Entire text italic (asterisk version)"),
    (
        "**Bold** and _italic_ separate",
        "Bold and italic separate",
        "Two separate styled ranges",
    ),
    (
        "Normal text with no formatting",
        "Normal text with no formatting",
        "No formatting",
    ),
]

print("COMPREHENSIVE MARKDOWN PARSER TESTS")
print("=" * 80)
print()

all_passed = True

for i, (input_text, expected_plain, description) in enumerate(test_cases, 1):
    print(f"Test {i}: {description}")
    print(f"  Input:    {input_text}")

    plain_text, styles = parse_inline_styles(input_text)

    print(f"  Output:   {plain_text}")
    print(f"  Expected: {expected_plain}")

    if plain_text == expected_plain:
        print(f"  ✓ PASS - Plain text correct")
    else:
        print(f"  ✗ FAIL - Plain text incorrect")
        all_passed = False

    print(f"  Styles: {len(styles)} range(s)")
    for j, style in enumerate(styles):
        styled_text = plain_text[style.start : style.end]
        formatting = []
        if style.bold:
            formatting.append("bold")
        if style.italic:
            formatting.append("italic")
        print(
            f"    [{style.start:2d}-{style.end:2d}] {'+'.join(formatting):12s} '{styled_text}'"
        )

    print()

print("=" * 80)
if all_passed:
    print("✓ ALL TESTS PASSED")
else:
    print("✗ SOME TESTS FAILED")
