import re
import sys

msg_file = sys.argv[1]

with open(msg_file, "r", encoding="utf-8") as f:
    msg = f.read().strip()

required_fields = [
    "ID:",
    "Description:",
    "Root Cause:",
    "Solution:"
]

for field in required_fields:
    if field not in msg:
        print(f"Missing '{field}' field.")
        sys.exit(1)

# pip install pre-commit
# py -m pre_commit install --hook-type commit-msg
# .pre-commit-config.yaml
# 