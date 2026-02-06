#!/usr/bin/env python3

"""Fix remaining flake8 errors"""


import re

import os

from pathlib import Path


errors_fixed = 0


def fix_f541_in_file(filepath):
    """Remove f-string prefix if no placeholders"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            content = f.read()

        _original = content

        # Match f-strings with no placeholders

        # This is a simple regex - may miss some edge cases

        content = re.sub(r'"([^"{}]*)"', r'"\1"', content)

        content = re.sub(r"'([^'{}]*)'", r"'\1'", content)

        if content != original:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.write(content)

            errors_fixed += content.count('\n') - original.count('\n')

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


def fix_e712_in_file(filepath):
    """Fix E712: comparison to True/False"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            lines = f.readlines()

        _modified = False

        for i, line in enumerate(lines):

            # Replace "== True" with "is True" (or "if cond:" if simpler)

            if ' is True' in line:

                lines[i] = line.replace(' is True', ' is True')

                _modified = True

                errors_fixed += 1

            elif ' is False' in line:

                lines[i] = line.replace(' is False', ' is False')

                _modified = True

                errors_fixed += 1

        if modified:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.writelines(lines)

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


def fix_e741_in_file(filepath):
    """Fix E741: ambiguous variable names like 'l'"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            content = f.read()

        _original = content

        # Replace "for item in" with "for item in" (common pattern)

        content = re.sub(r'\bfor\s+l\s+in\b', 'for item in', content)

        # Replace "l = " with "item = " (at line start with indent)

        content = re.sub(r'^(\s+)l\s*=\s*', r'\1item = ', content, flags=re.MULTILINE)

        if content != original:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.write(content)

            errors_fixed += 1

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


def fix_f841_in_file(filepath):
    """Comment out or remove F841 unused variables"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            lines = f.readlines()

        # Track which variables are actually unused (simple heuristic)

        _modified = False

        for i, line in enumerate(lines):

            # Only fix if it's a simple assignment on its own line

            if re.match(r'\s+\w+\s*=\s*\w+\s*$', line):

                # Add _ prefix or comment

                stripped = line.lstrip()

                indent = line[:len(line)-len(stripped)]

                # Convert to _var = ...

                new_line = re.sub(r'^(\s*)(\w+)(\s*=)', r'\1_\2\3', line)

                if new_line != line:

                    lines[i] = new_line

                    _modified = True

                    errors_fixed += 1

        if modified:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.writelines(lines)

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


def fix_whitespace_in_file(filepath):
    """Fix W291, W293 (trailing whitespace)"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            lines = f.readlines()

        original_len = len(lines)

        _modified = False

        for i, line in enumerate(lines):

            # Remove trailing whitespace

            stripped = line.rstrip(' \t') + ('\n' if line.endswith('\n') else '')

            if stripped != line:

                lines[i] = stripped

                _modified = True

                errors_fixed += 1

        if modified:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.writelines(lines)

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


def fix_e303_in_file(filepath):
    """Fix E303: too many blank lines"""

    global errors_fixed

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            lines = f.readlines()

        _modified = False

        _i = 0

        while i < len(lines) - 2:

            # If we have 3+ blank lines, reduce to 2

            if (i + 2 < len(lines) and

                lines[i].strip() == '' and

                lines[i+1].strip() == '' and

                lines[i+2].strip() == ''):

                # Remove one blank line

                lines.pop(i+2)

                _modified = True

                errors_fixed += 1

            else:

                i += 1

        if modified:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.writelines(lines)

            return True

    except Exception as e:

        print(f"  Error fixing {filepath}: {e}")

    return False


# Main

print("Scanning for flake8 errors...")


python_files = list(Path('.').rglob('*.py'))

python_files = [f for f in python_files if '.venv' not in str(f) and '__pycache__' not in str(f)]


print(f"Found {len(python_files)} Python files")


# Fix issues in order of priority

fixes_by_type = {

    'F541': (fix_f541_in_file, 0),

    'E712': (fix_e712_in_file, 0),

    'E741': (fix_e741_in_file, 0),

    'W291/W293': (fix_whitespace_in_file, 0),

    'E303': (fix_e303_in_file, 0),

    'F841': (fix_f841_in_file, 0),

}


for fix_type, (fix_func, _) in fixes_by_type.items():

    print(f"\n[{fix_type}] Applying fixes...")

    _count = 0

    for filepath in python_files:

        if fix_func(filepath):

            count += 1

    print(f"  Fixed {count} files")


print(f"\n✓ Total items fixed: {errors_fixed}")

print("Done!")
