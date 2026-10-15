#!/usr/bin/env python3 -I
"""Usage: summarize_junit.py REPORT.xml [max_failures]  -> <=15 lines. Works on gdUnit4 results.xml and GUT junit."""
import sys, re, xml.etree.ElementTree as ET
path, cap = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5
root = ET.parse(path).getroot()
tot = fail = skip = 0; fails = []
for tc in root.iter("testcase"):
    tot += 1
    f = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
    if tc.find("skipped") is not None: skip += 1
    if f is not None:
        fail += 1
        txt = (f.text or "") + " " + (f.get("message") or "")
        m = re.search(r"(res://\S+?:\d+)|at line (\d+)|line:?(\d+)", txt)   # gdUnit4: message="FAILED: res://x.gd:7"; GUT: "at line 7"
        loc = (m.group(1) or ("line " + (m.group(2) or m.group(3)))) if m else "?"
        first = next((l.strip() for l in (f.text or f.get("message") or "").splitlines() if l.strip() and not l.strip().startswith("<![")), "")
        fails.append(f"{tc.get('classname')}.{tc.get('name')} @ {loc}: {first[:100]}")
print(f"{'FAIL' if fail else 'PASS'}: {tot - fail - skip} passed, {fail} failed, {skip} skipped, {tot} total")
for line in fails[:cap]: print("  -", line)
if len(fails) > cap: print(f"  ... {len(fails) - cap} more")
