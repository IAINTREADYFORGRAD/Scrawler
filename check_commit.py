import re
import sys

msg_file = sys.argv[1]

with open(msg_file, "r", encoding="utf-8") as f:
    msg = f.read().strip()

pattern = (
    r"^ID: .+\n" # .+ 任意字元至少一個
    r"Description: .+\n" # r: raw string，Python 不要幫我處理跳脫字元，e.g., \n 就是兩個字元 '\' 和 'n'，而不是換行
    r"Root Cause: .+\n"
    r"Solution: .+"
)

if not re.match(pattern, msg, re.MULTILINE):
    print("Invalid commit message.")
    if not re.match(r"^ID: .+", msg, re.MULTILINE):
        print("Missing 'ID' field.")
    if not re.match(r"^Description: .+", msg, re.MULTILINE):
        print("Missing 'Description' field.")
    if not re.match(r"^Root Cause: .+", msg, re.MULTILINE):
        print("Missing 'Root Cause' field.")
    if not re.match(r"^Solution: .+", msg, re.MULTILINE):
        print("Missing 'Solution' field.")
    sys.exit(1)

# pip install pre-commit
# py -m pre_commit install --hook-type commit-msg
# .pre-commit-config.yaml
# 