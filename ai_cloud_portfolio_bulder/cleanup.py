with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Truncate at line 415 (the expected end of the file)
with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines[:415])
