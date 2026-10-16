#!/usr/bin/env python3
"""Run the five tests; print the counts. Exit 1 if anything is red."""
import os, re, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
names = [("1 mechanism", "test1_mechanism.py"), ("2 real thing", "test2_real_thing.py"),
         ("3 ugly cases", "test3_ugly_cases.py"), ("4 upgrade", "test4_upgrade.py"),
         ("5 termux", "test5_termux.py")]
total, red = 0, 0
for label, f in names:
    r = subprocess.run([sys.executable, os.path.join(here, f)], capture_output=True, text=True)
    out = r.stderr + r.stdout
    m = re.search(r"Ran (\d+) tests?", out)
    n = int(m.group(1)) if m else 0
    total += n
    status = "PASS" if r.returncode == 0 and n else "FAIL"
    if status == "FAIL":
        red += 1
        print(out[-3000:])
    print(f"TEST {label:14s} {status}  {n} checks")
print(f"{total} checks, {red} red")
sys.exit(1 if red else 0)
