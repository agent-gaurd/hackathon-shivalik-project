import re

with open("frontend/src/components/graph/MoneyMap.tsx", "r", encoding="utf-8") as f:
    text = f.read()

pattern = re.compile(r'(?:font-size|fontSize)\s*[:=]\s*["\']?([^"\'};,\n]+)["\']?')
all_sizes = pattern.findall(text)
print("Unique font-sizes in MoneyMap.tsx:")
for s in sorted(set(all_sizes)):
    print(" -", s)
