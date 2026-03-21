import os
import re

template_dir = r"c:\Users\krish\Desktop\management\frontend\templates"
pattern = re.compile(r'\son(click|change|submit|blur|focus|load)\s*=', re.IGNORECASE)

matches = []
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith(".html"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        matches.append(f"{path}:{i+1}:{line.strip()}\n")

with open(r"c:\Users\krish\Desktop\management\inline_handlers.txt", "w", encoding="utf-8") as f:
    f.writelines(matches)
