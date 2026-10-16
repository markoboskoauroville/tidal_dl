#!/usr/bin/env python3
"""Generate docs/index.html (a GitHub Pages page with a real Copy button per
command) and the copy link under each command block in README.md.

    python3 tools/build_copy_page.py            write README.md links + docs/index.html
    python3 tools/build_copy_page.py --check    exit 1 if either is stale

Why this exists (mantra_manifest modules/copy-buttons.md): GitHub's website puts
a copy button on every code block, but the GitHub app on Android draws the block
with no button at all - and that is the renderer Marko actually holds. Markdown
cannot carry a button, so the only button the app can reach is on a page the app
can open. So every `sh` command block in the README gets a link under it to a
card on this page, and the card has a full-width Copy button that shows the whole
command wrapped and never cut off.

The page is generated from the README, never typed: a command written in both is
two copies with a rule about keeping them in step (README rule 1). The gate runs
--check, which fails when a card is stale, a command has no link under it, or a
link points at nothing.
"""
import os, re, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
PAGE = os.path.join(ROOT, "docs", "index.html")
BASE_URL = "https://markoboskoauroville.github.io/tidal_dl/"
LINK_RE = re.compile(r"^✉️? ?\[Copy this command\]\(.*#cmd-\d+\)\s*$")
# the actual marker we write (clipboard emoji + link); detected for idempotency
COPY_LINK = re.compile(r"^\U0001F4CB \[Copy this command\]\([^)]*#cmd-\d+\)\s*$")


def parse(readme_lines):
    """Return (commands, link_positions). commands is a list of dicts with the
    command text and a title; link_positions maps the index of an existing copy
    link line to nothing (we just strip them). Only ```sh fenced blocks count."""
    commands = []
    i = 0
    n = len(readme_lines)
    while i < n:
        line = readme_lines[i]
        if line.strip() == "```sh":
            body = []
            j = i + 1
            while j < n and readme_lines[j].strip() != "```":
                body.append(readme_lines[j].rstrip("\n"))
                j += 1
            cmd = "\n".join(body).strip()
            title = find_title(readme_lines, i)
            commands.append({"cmd": cmd, "title": title, "fence_end": j})
            i = j + 1
        else:
            i += 1
    return commands


def find_title(lines, fence_start):
    """A short label for a command: the nearest bold-only line or heading above
    the block (within a few lines), else the first word of the command."""
    for k in range(fence_start - 1, max(-1, fence_start - 5), -1):
        s = lines[k].strip()
        if not s:
            continue
        m = re.match(r"^\*\*(.+?)\*\*", s)          # **bold label: ...**
        if m:
            return re.split(r"[:.]", m.group(1))[0].strip()
        m = re.match(r"^#{1,6}\s+(.+)$", s)          # heading
        if m:
            return m.group(1).strip()
        break                                        # a plain prose line: stop
    return None


def strip_links(lines):
    """Remove any existing copy-link lines (and a blank line they introduced) so
    regeneration is idempotent."""
    out = []
    for ln in lines:
        if COPY_LINK.match(ln.strip()):
            # drop the blank line we inserted just before the link, so a rebuild
            # reproduces the file byte for byte (idempotent)
            if out and out[-1].strip() == "":
                out.pop()
            continue
        out.append(ln)
    return out


def inject_links(lines, commands):
    """Insert a copy link line right after each ```sh block's closing fence."""
    # recompute fence ends on the stripped text
    cmds = parse(lines)
    assert len(cmds) == len(commands), "command count changed while injecting"
    out = []
    insert_after = {c["fence_end"]: idx + 1 for idx, c in enumerate(cmds)}
    for i, ln in enumerate(lines):
        out.append(ln)
        if i in insert_after:
            num = insert_after[i]
            out.append("\n")
            out.append(f"\U0001F4CB [Copy this command]({BASE_URL}#cmd-{num})\n")
    return out


def render_page(commands):
    cards = []
    for idx, c in enumerate(commands, 1):
        title = html.escape(c["title"] or f"Command {idx}")
        cmd_attr = html.escape(c["cmd"], quote=True)
        cmd_text = html.escape(c["cmd"])
        cards.append(f"""      <section class="card" id="cmd-{idx}">
        <h2>{title}</h2>
        <pre><code>{cmd_text}</code></pre>
        <button class="copy" data-cmd="{cmd_attr}">Copy command</button>
        <p class="hint" aria-live="polite"></p>
      </section>""")
    cards_html = "\n".join(cards)
    return PAGE_TEMPLATE.replace("@@CARDS@@", cards_html)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tidal DL — copy commands</title>
<meta name="description" content="One-press copy for every Tidal DL terminal command, for the GitHub Android app which shows no copy button.">
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d; --fg: #e6edf3;
    --muted: #8b949e; --accent: #2f81f7; --accent-fg: #ffffff; --ok: #3fb950;
    --code: #010409;
  }
  @media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) {
      --bg: #ffffff; --card: #f6f8fa; --border: #d0d7de; --fg: #1f2328;
      --muted: #59636e; --accent: #0969da; --accent-fg: #ffffff; --ok: #1a7f37;
      --code: #f6f8fa;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 16px;
  }
  .wrap { max-width: 720px; margin: 0 auto; }
  header { padding: 8px 0 4px; }
  h1 { font-size: 1.4rem; margin: 0 0 4px; }
  header p { color: var(--muted); margin: 0 0 20px; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; margin: 0 0 16px; scroll-margin-top: 12px;
  }
  .card:target { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent); }
  .card h2 { font-size: 1.05rem; margin: 0 0 10px; }
  pre {
    background: var(--code); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; margin: 0 0 12px; overflow-x: auto;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 0.92rem; white-space: pre-wrap; word-break: break-word;
  }
  button.copy {
    width: 100%; padding: 14px; font-size: 1rem; font-weight: 600;
    color: var(--accent-fg); background: var(--accent); border: 0; border-radius: 8px;
    cursor: pointer; -webkit-tap-highlight-color: transparent;
  }
  button.copy:active { opacity: 0.85; }
  button.copy.done { background: var(--ok); }
  .hint { color: var(--muted); font-size: 0.85rem; min-height: 1.2em; margin: 8px 0 0; }
  footer { color: var(--muted); font-size: 0.82rem; margin: 24px 0 8px; text-align: center; }
  footer a { color: var(--accent); }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Tidal DL — copy commands</h1>
      <p>Tap <strong>Copy command</strong>, then paste into your terminal. Made because the GitHub app on Android shows no copy button on code blocks.</p>
    </header>
@@CARDS@@
    <footer>
      Generated from the <a href="https://github.com/markoboskoauroville/tidal_dl/blob/main/README.md">README</a>. Do not edit this page by hand.
    </footer>
  </div>
<script>
(function () {
  function flash(btn, hint, msg, ok) {
    if (ok) { btn.classList.add("done"); var t = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.classList.remove("done"); btn.textContent = t; }, 1600); }
    hint.textContent = msg || "";
  }
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", "");
    ta.style.position = "absolute"; ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select(); ta.setSelectionRange(0, text.length);
    var ok = false; try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  document.querySelectorAll("button.copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-cmd");
      var hint = btn.parentElement.querySelector(".hint");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () { flash(btn, hint, "", true); },
          function () { flash(btn, hint, legacyCopy(text) ? "" : "Could not copy automatically — long-press the command above to copy it.", legacyCopy(text)); }
        );
      } else {
        var ok = legacyCopy(text);
        flash(btn, hint, ok ? "" : "Could not copy automatically — long-press the command above to copy it.", ok);
      }
    });
  });
})();
</script>
</body>
</html>
"""


def build():
    with open(README) as f:
        lines = f.readlines()
    commands = parse(lines)
    stripped = strip_links(lines)
    new_readme = "".join(inject_links(stripped, commands))
    page = render_page(commands)
    return new_readme, page, commands


def main():
    check = "--check" in sys.argv
    new_readme, page, commands = build()
    cur_readme = open(README).read()
    cur_page = open(PAGE).read() if os.path.exists(PAGE) else None
    if check:
        problems = []
        if not commands:
            problems.append("no ```sh command blocks found in README")
        if cur_readme != new_readme:
            problems.append("README copy links are stale")
        if cur_page != page:
            problems.append("docs/index.html is stale")
        # every command has exactly one card and one link, anchors line up
        anchors = re.findall(r'id="cmd-(\d+)"', page)
        links = re.findall(r"#cmd-(\d+)\)", new_readme)
        if sorted(anchors) != sorted(links) or len(anchors) != len(commands):
            problems.append("card/link anchors do not line up with the commands")
        if problems:
            for p in problems:
                print("STALE:", p)
            sys.exit(1)
        print(f"fresh: {len(commands)} commands, docs/index.html and README links in sync")
        sys.exit(0)
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(README, "w") as f:
        f.write(new_readme)
    with open(PAGE, "w") as f:
        f.write(page)
    print(f"wrote README.md copy links and docs/index.html ({len(commands)} commands)")


if __name__ == "__main__":
    main()
