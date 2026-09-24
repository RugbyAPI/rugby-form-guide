#!/usr/bin/env python3
"""
rugby-form-guide: the fixtures ahead in a competition, with each team's recent form,
points for and against, home and away record, and the head-to-head. One command, start to finish.

    python form_guide.py                          pick a competition with the arrow keys
    python form_guide.py --competition "Top 14"   straight to it
    python form_guide.py --competition cp_1ACRS3C --json > guide.json

Everything comes from the public rugbyAPI (https://rugbyapi.com/documentation). Standard library only.
"""
import argparse, datetime as dt, hashlib, json, os, sys, threading, time, itertools
import urllib.request, urllib.error, urllib.parse

BASE = os.environ.get("RUGBYAPI_BASE", "https://api.rugbyapi.com").rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
KEY_FILE = os.path.join(os.path.expanduser("~"), ".rugbyapi", "key")
TTL = {"competitions": 86400, "fixtures": 1800, "form": 6 * 3600, "h2h": 6 * 3600, "matches": 6 * 3600, "usage": 0}
VERSION = "1.0.0"

# ------------------------------------------------------------------ terminal look
if os.name == "nt":
    os.system("")  # turns on ANSI colours in Windows terminals
USE_COLOUR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
def c(code, s): return f"\033[{code}m{s}\033[0m" if USE_COLOUR else str(s)
GREEN, LIME, AMBER, RED, WHITE, SOFT, BORDER, BOLD = "38;5;35", "38;5;150", "38;5;214", "38;5;203", "97", "38;5;252", "38;5;240", "1"
W = 78

def vis_len(s):
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            j = s.find("m", i); i = j + 1 if j != -1 else len(s); continue
        out += 1; i += 1
    return out

def pad(s, n): return s + " " * max(0, n - vis_len(s))

def strip(s):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)

def box(title, lines, colour=GREEN):
    import textwrap
    top = c(BORDER, "\u256d\u2500 ") + c(colour + ";1", title) + " " + c(BORDER, "\u2500" * max(0, W - vis_len(title) - 5) + "\u256e")
    print(top)
    fitted = []
    for l in lines:
        if vis_len(l) <= W - 4: fitted.append(l); continue
        colour_of = l[:l.find("m") + 1] if l.startswith("\033[") else ""
        for part in textwrap.wrap(strip(l), W - 4): fitted.append(c(colour_of[2:-1], part) if colour_of else part)
    for l in fitted:
        print(c(BORDER, "\u2502 ") + pad(l, W - 4) + c(BORDER, " \u2502"))
    print(c(BORDER, "\u2570" + "\u2500" * (W - 2) + "\u256f"))

def bar(frac, width=16, colour=GREEN):
    frac = max(0.0, min(1.0, frac))
    full = int(round(frac * width))
    return c(colour, "\u2588" * full) + c(BORDER, "\u2591" * (width - full))

def form_chips(s):
    col = {"W": GREEN, "D": AMBER, "L": RED}
    return " ".join(c(col.get(ch, BORDER) + (";1" if ch in col else ""), ch if ch in col else "\u00b7") for ch in s) if s.strip("-") else c(SOFT, "no recent matches")

class Spinner:
    def __init__(self, text): self.text, self.stop = text, threading.Event()
    def __enter__(self):
        if sys.stdout.isatty():
            self.t = threading.Thread(target=self.spin, daemon=True); self.t.start()
        return self
    def spin(self):
        for ch in itertools.cycle("\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"):
            if self.stop.is_set(): break
            sys.stdout.write("\r" + c(LIME, ch) + " " + c(SOFT, self.text) + "   "); sys.stdout.flush(); time.sleep(0.08)
        sys.stdout.write("\r" + " " * (vis_len(self.text) + 6) + "\r"); sys.stdout.flush()
    def update(self, text): self.text = text
    def __exit__(self, *a):
        self.stop.set()
        if hasattr(self, "t"): self.t.join()

# ------------------------------------------------------------------ arrow-key menu
def read_key():
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
        return {"\r": "enter", "\x1b": "esc", "\x03": "quit"}.get(ch, ch)
    import termios, tty
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd); ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            return {"[A": "up", "[B": "down"}.get(seq, "esc")
        return {"\r": "enter", "\n": "enter", "\x03": "quit"}.get(ch, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def menu(title, items, label):
    """Arrow keys to move, Enter to choose. Shows 12 at a time."""
    idx, top, view = 0, 0, 12
    print(c(WHITE + ";1", title) + c(SOFT, "   (arrow keys, Enter to choose)"))
    drawn = 0
    while True:
        if drawn: sys.stdout.write(f"\033[{drawn}F")
        top = min(max(top, idx - view + 1), idx)
        rows = items[top:top + view]
        for i, it in enumerate(rows):
            on = top + i == idx
            line = (c(LIME + ";1", "\u276f ") + c(WHITE + ";1", label(it))) if on else ("  " + c(SOFT, label(it)))
            sys.stdout.write("\033[2K" + line + "\n")
        more = f"{top + 1}-{top + len(rows)} of {len(items)}"
        sys.stdout.write("\033[2K" + c(BORDER, "  " + more) + "\n"); sys.stdout.flush()
        drawn = len(rows) + 1
        k = read_key()
        if k == "up": idx = (idx - 1) % len(items)
        elif k == "down": idx = (idx + 1) % len(items)
        elif k == "enter": return items[idx]
        elif k in ("quit", "esc", "q"): print(); sys.exit(0)

# ------------------------------------------------------------------ API with cache and pacing
class Api:
    def __init__(self, key):
        self.key, self.remaining, self.limit, self.calls = key, None, None, 0

    def get(self, path, params=None, kind="matches"):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        os.makedirs(DATA, exist_ok=True)
        cache = os.path.join(DATA, kind + "-" + hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
        ttl = TTL.get(kind, 3600)
        if ttl and os.path.exists(cache) and time.time() - os.path.getmtime(cache) < ttl:
            with open(cache, encoding="utf-8") as f: return json.load(f)
        if self.remaining is not None and self.remaining <= 1:
            raise ApiError(429, "daily_limit", "Today's lookups are used. The count resets at 00:00 UTC.")
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.key, "User-Agent": "rugby-form-guide/" + VERSION})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode("utf-8"))
                self.track(r.headers)
        except urllib.error.HTTPError as e:
            self.track(e.headers)
            try: err = json.loads(e.read().decode("utf-8")).get("error", {})
            except Exception: err = {}
            raise ApiError(e.code, err.get("code", "http_" + str(e.code)), err.get("message", str(e)))
        except urllib.error.URLError as e:
            raise ApiError(0, "network", "Could not reach " + BASE + ": " + str(e.reason))
        self.calls += 1
        if ttl:
            with open(cache, "w", encoding="utf-8") as f: json.dump(body, f)
        # pace by what the plan allows: gentler as the allowance runs down
        if self.remaining is not None and self.limit:
            time.sleep(0.15 if self.remaining > self.limit * 0.2 else 0.6)
        return body

    def track(self, headers):
        try:
            if headers.get("X-RateLimit-Remaining") is not None: self.remaining = int(headers["X-RateLimit-Remaining"])
            if headers.get("X-RateLimit-Limit") is not None: self.limit = int(headers["X-RateLimit-Limit"])
        except (TypeError, ValueError): pass

class ApiError(Exception):
    def __init__(self, status, code, message): super().__init__(message); self.status, self.code, self.message = status, code, message

def load_key(json_mode):
    env = os.environ.get("RUGBYAPI_KEY")
    if env: return env.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f: return f.read().strip()
    if json_mode:
        sys.stderr.write("No API key: set RUGBYAPI_KEY or run once without --json to save it.\n"); sys.exit(2)
    box("rugbyAPI key", ["Paste your key from https://rugbyapi.com/account", c(SOFT, "It is saved to " + KEY_FILE + " so you are only asked once.")], LIME)
    key = input(c(WHITE + ";1", "Key: ")).strip()
    if not key.startswith("rug_"):
        print(c(RED, "That does not look like a rugbyAPI key (they start rug_live_).")); sys.exit(1)
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "w", encoding="utf-8") as f: f.write(key)
    try: os.chmod(KEY_FILE, 0o600)
    except OSError: pass
    return key

# ------------------------------------------------------------------ the guide
def team_profile(api, team_id):
    """Last 10 finished matches: form (last 5), points for and against, home and away records."""
    body = api.get(f"/v1/teams/{team_id}/form", {"last": 10}, "form")
    rows = body.get("data", [])
    pf = pa = 0; home = {"W": 0, "D": 0, "L": 0}; away = {"W": 0, "D": 0, "L": 0}
    for m in rows:
        is_home = m["home"]["id"] == team_id
        us, them = (m["home"], m["away"]) if is_home else (m["away"], m["home"])
        pf += us["score"] or 0; pa += them["score"] or 0
        (home if is_home else away)[m["result"]] += 1
    n = len(rows) or 1
    last5 = "".join(m["result"] for m in rows[:5])
    return {"name": body.get("team", {}).get("name"), "form": last5, "played": len(rows),
            "wins_last5": last5.count("W"), "pf_avg": round(pf / n, 1), "pa_avg": round(pa / n, 1),
            "home": home, "away": away}

def rec(r): return f"{r['W']}-{r['D']}-{r['L']}"

def build(api, comp, days, progress=None):
    fx = api.get("/v1/fixtures", {"competition": comp["id"], "days": days}, "fixtures").get("data", [])
    teams, out = {}, []
    for i, m in enumerate(fx):
        if progress: progress(f"{m['home']['name']} v {m['away']['name']}  ({i + 1} of {len(fx)})")
        for side in ("home", "away"):
            tid = m[side]["id"]
            if tid not in teams: teams[tid] = team_profile(api, tid)
        h2h = api.get("/v1/head-to-head", {"team_a": m["home"]["id"], "team_b": m["away"]["id"]}, "h2h")
        out.append({"match": m, "home": teams[m["home"]["id"]], "away": teams[m["away"]["id"]],
                    "h2h": h2h.get("summary", {}), "last_meeting": (h2h.get("data") or [None])[0]})
    return out

def when(m):
    if m.get("kickoff_utc"):
        t = dt.datetime.strptime(m["kickoff_utc"], "%Y-%m-%dT%H:%M:%SZ")
        return t.strftime("%a %d %b, %H:%M UTC")
    return dt.datetime.strptime(m["date"], "%Y-%m-%d").strftime("%a %d %b") + ", time to be set"

def show(guide, comp, api):
    for g in guide:
        m, a, b, h = g["match"], g["home"], g["away"], g["h2h"]
        nw = 24
        lines = [c(SOFT, when(m)), ""]
        for t, tag in ((a, "home"), (b, "away")):
            lines.append(c(WHITE + ";1", pad(t["name"][:nw], nw)) + "  " + pad(form_chips(t["form"].rjust(5, "-")), 9) + "   " + bar(t["wins_last5"] / 5, 10) + " " + c(SOFT, f"{t['wins_last5']}/5 won"))
            lines.append(" " * (nw + 2) + c(SOFT, f"scores {t['pf_avg']:>4} conc {t['pa_avg']:>4}  home {rec(t['home'])}  away {rec(t['away'])}"))
        lines.append("")
        if h.get("played"):
            share = h["team_a_wins"] / h["played"]
            lines.append(c(SOFT, f"Met {h['played']}x  ") + bar(share, 12, LIME) + "  " + c(WHITE, f"{a['name'][:16]} {h['team_a_wins']}") + c(SOFT, f"  drawn {h['draws']}  ") + c(WHITE, f"{b['name'][:16]} {h['team_b_wins']}"))
            lm = g["last_meeting"]
            if lm: lines.append(c(SOFT, f"Last met {lm['date']}: {lm['home']['name']} {lm['home']['score']}-{lm['away']['score']} {lm['away']['name']}"))
        else:
            lines.append(c(SOFT, "Head to head: no meetings on record"))
        box(f"{m['home']['name']} v {m['away']['name']}", lines)
    left = f"{api.remaining} lookups left today" if api.remaining is not None else ""
    print(c(SOFT, f"{len(guide)} fixture{'s' if len(guide) != 1 else ''} in {comp['name']}  \u00b7  {api.calls} lookups used this run, the rest came from ./data  \u00b7  {left}"))

def main():
    ap = argparse.ArgumentParser(description="Form guide for the fixtures ahead, from rugbyAPI.")
    ap.add_argument("--competition", help="competition ID (cp_...) or name, e.g. \"Top 14\"")
    ap.add_argument("--days", type=int, default=14, help="how many days ahead, 1 to 60 (default 14)")
    ap.add_argument("--json", action="store_true", help="print only the guide as JSON, no prompts")
    args = ap.parse_args()
    days = max(1, min(60, args.days))
    key = load_key(args.json)
    api = Api(key)
    try:
        usage = api.get("/v1/usage", kind="usage")
    except ApiError as e:
        msg = e.message if e.status != 401 else "That key was refused: " + e.message
        if args.json: sys.stderr.write(msg + "\n"); sys.exit(1)
        box("Key check failed", [c(RED, msg), c(SOFT, "Rotate or copy your key at https://rugbyapi.com/account")], RED)
        if e.status == 401 and os.path.exists(KEY_FILE): os.remove(KEY_FILE)
        sys.exit(1)
    api.remaining, api.limit = usage.get("remaining"), usage.get("limit")
    if not args.json:
        plan = {"free": "Free key", "archive": "Archive", "live": "Live"}.get(usage.get("plan"), usage.get("plan"))
        box("rugby-form-guide " + VERSION, [c(WHITE + ";1", "Plan: ") + c(LIME + ";1", plan) + c(SOFT, f"   {usage.get('remaining')} of {usage.get('limit')} lookups left today"),
                                            c(SOFT, "Cached answers in ./data are reused, so running again costs little.")], LIME)
    comps = sorted(api.get("/v1/competitions", kind="competitions").get("data", []), key=lambda x: x["name"])
    comp = None
    if args.competition:
        want = args.competition.strip().lower()
        comp = next((x for x in comps if x["id"].lower() == want or x["name"].lower() == want), None) \
            or next((x for x in comps if want in x["name"].lower()), None)
        if not comp:
            msg = f"No competition matches '{args.competition}'."
            if args.json: sys.stderr.write(msg + "\n"); sys.exit(2)
            print(c(RED, msg)); sys.exit(2)
    elif args.json:
        sys.stderr.write("--json needs --competition (an ID such as cp_1ACRS3C, or a name).\n"); sys.exit(2)
    else:
        print()
        comp = menu("Which competition?", comps, lambda x: f"{x['name']}  " + c(BORDER, (x.get('region') or '')))
        print()
    try:
        if args.json:
            guide = build(api, comp, days)
        else:
            with Spinner("Fetching fixtures") as sp:
                guide = build(api, comp, days, sp.update)
    except ApiError as e:
        if e.code == "plan_required":
            msg = ["Team form and head-to-head come from past seasons, which need the Archive plan.",
                   "A free key covers yesterday, today and the fixtures ahead.",
                   c(LIME + ";1", "Upgrade at https://rugbyapi.com/pricing")]
            if args.json: sys.stderr.write(" ".join(msg[:2]) + "\n"); sys.exit(3)
            box("This guide needs Archive", msg, AMBER); sys.exit(3)
        if args.json: sys.stderr.write(e.message + "\n"); sys.exit(1)
        box("Stopped", [c(RED, e.message)], RED); sys.exit(1)
    if args.json:
        print(json.dumps({"tool": "rugby-form-guide", "version": VERSION, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "criteria": {"competition": {"id": comp["id"], "name": comp["name"]}, "days_ahead": days,
                                       "form": "last 5 finished matches", "averages_and_splits": "last 10 finished matches",
                                       "head_to_head": "every finished meeting on record", "excluded": "matches flagged as duplicates by rugbyAPI"},
                          "fixtures": guide}, indent=2))
        return
    if not guide:
        box(comp["name"], [c(SOFT, f"No fixtures in the next {days} days."), c(SOFT, "Try --days 60, or another competition.")], AMBER); return
    show(guide, comp, api)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print(); sys.exit(130)
