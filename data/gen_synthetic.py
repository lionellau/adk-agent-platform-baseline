"""Regenerate the synthetic media dataset (fictional titles) and print the reference answers.

Usage:
  python3 data/gen_synthetic.py           # rewrite the two CSVs next to this script
  python3 data/gen_synthetic.py --check   # only compare with the committed CSVs (no writes)
"""

import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CATALOGUE = [
    ("C001", "Harbour Evening News", "news", "news", "English", "2026-01-05", 30),
    ("C002", "Island Talk", "news", "current_affairs", "English", "2026-02-10", 45),
    ("C003", "Market Pulse", "news", "business", "English", "2026-03-01", 25),
    ("C004", "Berita Malam", "news", "news", "Malay", "2026-02-01", 30),
    ("C005", "Seithi Tonight", "news", "news", "Tamil", "2026-02-01", 30),
    ("C006", "Kopi Kitchen", "entertainment", "lifestyle", "English", "2026-01-20", 22),
    ("C007", "Lion City Hearts", "entertainment", "drama", "English", "2026-04-15", 40),
    (
        "C008",
        "Star Search Stage",
        "entertainment",
        "variety",
        "Mandarin",
        "2026-05-02",
        60,
    ),
    (
        "C009",
        "Merlion Mysteries",
        "entertainment",
        "drama",
        "English",
        "2026-06-11",
        42,
    ),
    (
        "C010",
        "Hawker Love Story",
        "entertainment",
        "drama",
        "Mandarin",
        "2026-07-07",
        45,
    ),
]
WEEKS = ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
BASE = {
    "C001": 52000,
    "C002": 18000,
    "C003": 9500,
    "C004": 14000,
    "C005": 8000,
    "C006": 21000,
    "C007": 47000,
    "C008": 39000,
    "C009": 51000,
    "C010": 33000,
}
STEP = {
    "C001": -1000,
    "C002": 500,
    "C003": 200,
    "C004": -300,
    "C005": 100,
    "C006": 800,
    "C007": 2500,
    "C008": -1500,
    "C009": -2000,
    "C010": 3000,
}


def build():
    minutes = {c[0]: c[6] for c in CATALOGUE}
    views = []
    for i, day in enumerate(WEEKS):
        for cid in BASE:
            v = BASE[cid] + STEP[cid] * i
            platform = "mewatch" if (int(cid[1:]) + i) % 2 == 0 else "tv"
            views.append((day, cid, platform, v, int(v * minutes[cid] * 0.6)))
    return views


def to_csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def main():
    views = build()
    files = {
        "content_catalogue.csv": to_csv(
            [
                "content_id",
                "title",
                "business_unit",
                "genre",
                "language",
                "release_date",
                "duration_min",
            ],
            CATALOGUE,
        ),
        "daily_viewership.csv": to_csv(
            ["view_date", "content_id", "platform", "views", "watch_minutes"], views
        ),
    }
    if "--check" in sys.argv:
        ok = all(
            open(os.path.join(HERE, n)).read() == body for n, body in files.items()
        )
        print(
            "CSV files match the generator"
            if ok
            else "FIX: CSV files differ from the generator"
        )
        sys.exit(0 if ok else 1)
    for name, body in files.items():
        with open(os.path.join(HERE, name), "w") as f:
            f.write(body)
        print("wrote", name)

    title = {c[0]: (c[1], c[2]) for c in CATALOGUE}
    total = {}
    for _, cid, _, v, _ in views:
        total[cid] = total.get(cid, 0) + v
    print("Reference answers (October 2026):")
    for cid in sorted(total, key=lambda c: -total[c])[:3]:
        print(f"  {title[cid][0]}: {total[cid]:,} views")
    by_bu = {}
    for cid, v in total.items():
        by_bu[title[cid][1]] = by_bu.get(title[cid][1], 0) + v
    print("  by business unit:", {k: f"{v:,}" for k, v in sorted(by_bu.items())})


if __name__ == "__main__":
    main()
