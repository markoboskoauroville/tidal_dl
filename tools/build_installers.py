#!/usr/bin/env python3
"""Generate install-macos.sh and install-termux.sh from src/*.sh.in and tidaldl.py.

    python3 tools/build_installers.py            write both
    python3 tools/build_installers.py --check    exit 1 if a shipped installer is stale

tidaldl.py is the only copy of the program; the installers carry it verbatim.
"""
import hashlib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = [("src/macos.sh.in", "install-macos.sh"), ("src/termux.sh.in", "install-termux.sh")]

def read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()

def build(tpl_rel):
    py = read("tidaldl.py").rstrip("\n")
    tpl = read(tpl_rel)
    version = re.search(r"^VERSION = (\d+)$", py, re.M).group(1)
    if "\nPYEOF\n" in py or py.startswith("PYEOF\n"):
        sys.exit("tidaldl.py contains a PYEOF line; it would end the heredoc early")
    h = hashlib.sha256((tpl + py).encode()).hexdigest()[:16]
    return (tpl.replace("@@VERSION@@", version).replace("@@HASH@@", h)
               .replace("@@TIDALDL_PY@@", py))

def main():
    check = "--check" in sys.argv
    stale = 0
    for tpl, out in TARGETS:
        text = build(tpl)
        path = os.path.join(ROOT, out)
        current = open(path).read() if os.path.exists(path) else None
        if check:
            if current != text:
                print(f"STALE: {out} does not match its sources")
                stale += 1
            else:
                print(f"fresh: {out}")
        else:
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)
            print(f"wrote {out}")
    sys.exit(1 if stale else 0)

if __name__ == "__main__":
    main()
