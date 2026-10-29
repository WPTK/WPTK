"""Fill the generated sections of README.md: books (StoryGraph export), planes (skystats) and the blog (blog.wptk.org).

Each section sits between <!-- NAME:START --> and <!-- NAME:END --> markers. A source that fails leaves its section
as it was. With --push, commits and pushes README.md when it changed.

Local settings come from local.env (git-ignored): SG_EXPORT, SG_LIBRARY, SKYSTATS_DSN.
"""
import csv
import datetime as dt
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(ROOT, "README.md")
UA = "WPTK-profile-readme/1.0 (https://github.com/WPTK/WPTK)"

TYPES = {
    "A20N": "Airbus A320neo", "A21N": "Airbus A321neo", "A319": "Airbus A319", "A320": "Airbus A320",
    "A321": "Airbus A321", "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900",
    "A359": "Airbus A350-900", "BCS1": "Airbus A220-100", "BCS3": "Airbus A220-300",
    "B712": "Boeing 717", "B737": "Boeing 737-700", "B738": "Boeing 737-800", "B739": "Boeing 737-900",
    "B38M": "Boeing 737 MAX 8", "B39M": "Boeing 737 MAX 9", "B752": "Boeing 757-200", "B753": "Boeing 757-300",
    "B763": "Boeing 767-300", "B764": "Boeing 767-400", "B772": "Boeing 777-200", "B77W": "Boeing 777-300ER",
    "B788": "Boeing 787-8", "B789": "Boeing 787-9", "B78X": "Boeing 787-10",
    "CRJ2": "Bombardier CRJ200", "CRJ7": "Bombardier CRJ700", "CRJ9": "Bombardier CRJ900",
    "E145": "Embraer ERJ-145", "E170": "Embraer E170", "E75L": "Embraer E175", "E75S": "Embraer E175",
    "E190": "Embraer E190", "C172": "Cessna 172", "PC12": "Pilatus PC-12", "C56X": "Cessna Citation Excel",
    "E55P": "Embraer Phenom 300", "E50P": "Embraer Phenom 100", "E545": "Embraer Legacy 450",
    "E550": "Embraer Praetor 600", "C68A": "Cessna Citation Latitude", "C700": "Cessna Citation Longitude",
    "CL35": "Bombardier Challenger 350", "GLF4": "Gulfstream IV", "GLF5": "Gulfstream V", "GLF6": "Gulfstream G650",
    "BE20": "Beechcraft King Air 200", "B350": "Beechcraft King Air 350", "SR22": "Cirrus SR22",
}


FORMATS = {"audio": "Audiobook", "digital": "eBook", "paperback": "Paperback", "hardcover": "Hardcover"}


def load_env():
    path = os.path.join(ROOT, "local.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k and not k.startswith("#"):
                os.environ.setdefault(k, v)


def replace(text, name, body):
    pat = re.compile(r"(<!-- %s:START -->\n).*?(<!-- %s:END -->)" % (name, name), re.S)
    return pat.sub(lambda m: m.group(1) + body.rstrip() + "\n" + m.group(2), text)


# Books

def _date(s):
    return dt.datetime.strptime(s, "%Y/%m/%d").date() if s else dt.date.min


def _key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _day(d, month="%B"):
    return "%s %d" % (d.strftime(month), d.day)


def _book(r, scores):
    line = "**%s** by %s" % (r["Title"], r["Authors"])
    score = scores.get(_key(r["Title"]))
    if score:
        line += " · %s" % score
    if r["Last Date Read"]:
        d = _date(r["Last Date Read"])
        line += " · " + _day(d, "%b") + ", %d" % d.year
    return line


def books():
    rows = list(csv.DictReader(open(os.environ["SG_EXPORT"], encoding="utf-8-sig")))
    library = list(csv.DictReader(open(os.environ["SG_LIBRARY"], encoding="utf-8-sig")))
    scores = {_key(r["Title"]): r["C3L Rating"] for r in library if r["C3L Rating"]}
    done = sorted((r for r in rows if r["Read Status"] == "read"), key=lambda r: _date(r["Last Date Read"]), reverse=True)
    read = next((r for r in done if r["Format"] != "audio"), None)
    heard = next((r for r in done if r["Format"] == "audio"), None)
    now = [r for r in rows if r["Read Status"] == "currently-reading"]
    out = []
    if now:
        out.append("**Current:**  ")
        out += ["%s: %s *%s* by %s  " % (FORMATS.get(r["Format"], "Book"), "🎧" if r["Format"] == "audio" else "📖",
                                         r["Title"], r["Authors"]) for r in now]
        out.append("")
    if read:
        out.append("📖 **Last read:** " + _book(read, scores) + "  ")
    if heard:
        out.append("🎧 **Last listen:** " + _book(heard, scores) + "  ")
    out.append("")
    out.append("%d books rated so far, all of them at [wptk.org](https://wptk.org/ratings.html)." % len(library))
    return "\n".join(out)


# Planes

def planes():
    import psycopg
    with psycopg.connect(os.environ["SKYSTATS_DSN"], connect_timeout=10) as db:
        last = db.execute("select max(last_seen) from aircraft_data").fetchone()[0]
        since = "now() - interval '24 hours'"
        total = db.execute("select count(distinct hex) from aircraft_data where last_seen > %s" % since).fetchone()[0]
        if not total:
            return "_The receiver has been quiet since %s, %d._" % (_day(last, "%b"), last.year)
        types = db.execute("select t, count(distinct hex) n from aircraft_data where last_seen > %s and t <> ''"
                           " group by t order by n desc limit 5" % since).fetchall()
        carriers = db.execute("select r.airline_name, count(distinct a.hex) n from aircraft_data a"
                              " join route_data r on r.route_callsign = trim(a.flight)"
                              " where a.last_seen > %s and r.airline_name <> ''"
                              " group by 1 order by n desc limit 5" % since).fetchall()
    out = ["**%s aircraft** heard by my ADS-B receiver in the last 24 hours." % format(total, ","), "",
           "| Top types | | Top carriers | |", "|---|--:|---|--:|"]
    for i in range(max(len(types), len(carriers))):
        t = types[i] if i < len(types) else ("", "")
        c = carriers[i] if i < len(carriers) else ("", "")
        out.append("| %s | %s | %s | %s |" % (TYPES.get(t[0], t[0]), t[1], c[0], c[1]))
    return "\n".join(out)


# Blog

def blog():
    """The five newest posts in the blog's Atom feed, which lists only published posts (same as the homepage)."""
    req = urllib.request.Request("https://blog.wptk.org/feed.xml", headers={"User-Agent": UA})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = ["**Latest from [%s](https://blog.wptk.org)**" % root.find("a:title", ns).text, ""]
    # A list, not a table: GitHub sizes tables to their unwrapped width, so long titles overflow the page.
    for e in root.findall("a:entry", ns)[:5]:
        d = dt.date.fromisoformat(e.find("a:published", ns).text[:10])
        out.append("- %s, %d | [%s](%s)" % (_day(d, "%b"), d.year, e.find("a:title", ns).text,
                                           e.find("a:link", ns).get("href")))
    return "\n".join(out)


def main():
    load_env()
    text = open(README, encoding="utf-8").read()
    new = text
    for name, fn in (("BOOKS", books), ("PLANES", planes), ("BLOG", blog)):
        try:
            new = replace(new, name, fn())
        except Exception as e:
            print("%s: %s" % (name, e), file=sys.stderr)
    if new == text:
        print("no change")
        return 0
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("README.md updated")
    if "--push" in sys.argv:
        git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, check=True)
        git("add", "README.md")
        git("commit", "-q", "-m", "readme: refresh")
        git("push", "-q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
