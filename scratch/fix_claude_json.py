import os, json
path = os.path.expanduser("~/.claude.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

if "env" in data:
    env = data["env"]
    if "ANTHROPIC_AUTH_TOKEN" in env:
        del env["ANTHROPIC_AUTH_TOKEN"]
        print("Removed ANTHROPIC_AUTH_TOKEN from .claude.json")
    else:
        print("ANTHROPIC_AUTH_TOKEN not found in env")

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print("Updated .claude.json successfully!")
