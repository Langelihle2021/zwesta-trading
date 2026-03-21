#!/usr/bin/env python3
with open('multi_broker_backend_updated.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

in_string = False
start_line = 0

for i, line in enumerate(lines, 1):
    triple_count = line.count('"""')
    if triple_count % 2 == 1:
        in_string = not in_string
        if in_string:
            start_line = i
            
if in_string:
    print(f'Unclosed triple-quote from line {start_line}')
    print(f'Line {start_line}: {repr(lines[start_line-1][:100])}')
else:
    print('All triple-quotes are properly closed')
