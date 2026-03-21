#!/usr/bin/env python3
"""Script to collapse multi-line docstrings into single-line docstrings."""

import re

# Read the file
with open('multi_broker_backend_updated.py', 'r', encoding='utf-8', errors='replace') as f:
    original_content = f.read()

# Pattern to match multi-line docstrings
# This matches """ followed by content, followed by """
pattern = r'"""\s*\n\s*(.*?)\n\s*"""'

def replace_docstring(match):
    """Replace multi-line docstring with single-line version."""
    content = match.group(1)
    # Clean up the content - handle multi-line descriptions
    content = content.strip()
    # Replace newlines and extra whitespace with spaces
    content = re.sub(r'\s+', ' ', content)
    return f'"""{content}"""'

# Replace all multi-line docstrings
modified_content = re.sub(pattern, replace_docstring, original_content, flags=re.DOTALL)

# Write back
with open('multi_broker_backend_updated.py', 'w', encoding='utf-8') as f:
    f.write(modified_content)

print("✅ Multi-line docstrings collapsedto single-line format")

# Verify syntax
import ast
try:
    ast.parse(modified_content)
    print("✅ File syntax is valid")
except SyntaxError as e:
    print(f"❌ SyntaxError at line {e.lineno}: {e.msg}")
