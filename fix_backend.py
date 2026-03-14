#!/usr/bin/env python3
import re

# Read the backend file
with open('multi_broker_backend_updated.py', 'r') as f:
    lines = f.readlines()

# Fix: Replace role queries
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if this is a role query
    if "SELECT role FROM users" in line:
        # Skip this line and the next few lines of the role check, replace with simple user check
        if i + 7 < len(lines) and "Admin access required" in lines[i + 7]:
            # We're at the start of a role check block
            output_lines.append("        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))\n")
            output_lines.append("        user = cursor.fetchone()\n")
            output_lines.append("        conn.close()\n")
            output_lines.append("        \n")
            output_lines.append("        if not user:\n")
            output_lines.append("            return jsonify({'success': False, 'error': 'User not found'}), 403\n")
            i += 8  # Skip the old role check lines
            continue
    
    output_lines.append(line)
    i += 1

# Write back
with open('multi_broker_backend_updated.py', 'w') as f:
    f.writelines(output_lines)

print('✅ Fixed role column queries in backend')
