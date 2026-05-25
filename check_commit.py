import re
import sys

msg_file = sys.argv[1]

with open(msg_file, "r", encoding="utf-8") as f:
    msg = f.read().strip()

pattern = (
    r"^ID: .+\n" # .+ 任意字元至少一個
    r"description: .+\n" # r: raw string，Python 不要幫我處理跳脫字元，e.g., \n 就是兩個字元 '\' 和 'n'，而不是換行
    r"root cause: .+\n"
    r"solution: .+"
)

if not re.match(pattern, msg, re.MULTILINE):
    print("Invalid commit message.")
    print("ID|description|root cause|solution|")
    sys.exit(1)

# pip install pre-commit
# .pre-commit-config.yaml