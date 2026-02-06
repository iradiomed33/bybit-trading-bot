#!/usr/bin/env python

"""Fix F541 f-string errors by removing 'f' prefix when no placeholders"""

import re

import subprocess


# Find all F541 issues

f541_files = {}

result = subprocess.run(['python', '-m', 'flake8', '.', '--select=F541'],

                       capture_output=True, text=True)


for line in result.stdout.strip().split('\n'):

    if line:

        parts = line.split(':')

        if len(parts) >= 4:

            filepath = parts[0].lstrip('.\\/')

            linenum = int(parts[1])

            if filepath not in f541_files:

                f541_files[filepath] = []

            f541_files[filepath].append(linenum)


print(f"Found F541 in {len(f541_files)} files, {sum(len(v) for v in f541_files.values())} total")


# Read each file and fix

for filepath, lines in sorted(f541_files.items()):

    try:

        with open(filepath, 'r', encoding='utf-8') as f:

            content = f.read()

        lines_list = content.split('\n')

        _modified = False

        for linenum in sorted(lines, reverse=True):

            idx = linenum - 1

            if idx < len(lines_list):

                line = lines_list[idx]

                # Remove f from f-string if no placeholders

                new_line = re.sub(r"f(['\"])(.*?)\1", r"\1\2\1", line)

                if new_line != line:

                    lines_list[idx] = new_line

                    _modified = True

        if modified:

            with open(filepath, 'w', encoding='utf-8') as f:

                f.write('\n'.join(lines_list))

            print(f"  Fixed {filepath}")

    except Exception as e:

        print(f"  Error {filepath}: {e}")


print("\nDone!")
