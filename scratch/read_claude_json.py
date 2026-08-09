import os, json
path = os.path.expanduser("~/.claude.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
print(json.dumps(data.get("env"), indent=2))
