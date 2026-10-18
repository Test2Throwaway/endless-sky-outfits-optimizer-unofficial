import json, statistics, sys
from collections import defaultdict
from pathlib import Path
recs = [json.loads(p.read_text()) for p in Path(sys.argv[1]).glob("*.json")]
groups = defaultdict(list)
for r in recs:
    if r["raw"]:
        groups[(r["reference"], r["combine"], r["tweaks"])].append(r)
def ratio(r, k):
    s = r["stock"][k]
    return r["raw"][k] / s if s else None
rows = []
for (ref, comb, tw), rs in groups.items():
    per_hull = defaultdict(list)
    for r in rs: per_hull[r["hull"]].append(r)
    def med(fn):
        vals = [fn(r) for r in rs]; vals = [v for v in vals if v is not None]
        return statistics.median(vals) if vals else float("nan")
    kiv = per_hull["Kar Ik Vot 349"]
    rows.append({
        "config": f"{ref} / {comb} / {'tweaks' if tw else 'plain'}", "n": len(rs),
        "failed": sum(1 for r in rs if r["failed"]),
        "dps": med(lambda r: ratio(r, "raw dps")),
        "wspace": med(lambda r: r["raw"]["space weapons"] - r["stock"]["space weapons"]),
        "wcap": med(lambda r: r["raw"]["weapon capacity used"]),
        "kiv regen": statistics.median([ratio(r, "shield regen") for r in kiv]) if kiv else float("nan"),
        "kiv hull": statistics.median([ratio(r, "hull repair") for r in kiv]) if kiv else float("nan"),
        "kiv dps": statistics.median([ratio(r, "raw dps") for r in kiv]) if kiv else float("nan"),
        "kiv route": "/".join(sorted({r["route"].split(": ")[-1] for r in kiv})) if kiv else "",
        "turn": med(lambda r: ratio(r, "turn")), "accel": med(lambda r: ratio(r, "acceleration")),
        "speed": med(lambda r: ratio(r, "speed")),
        "guns": statistics.mean(r["raw"]["guns"] - r["stock"]["guns"] for r in rs),
        "secondary": statistics.mean(r["raw"]["secondary weapons"] for r in rs),
        "score spread": statistics.mean(
            (max(x["score"] for x in hr) - min(x["score"] for x in hr)) for hr in per_hull.values() if len(hr) > 1) if any(len(h) > 1 for h in per_hull.values()) else float("nan"),
    })
rows.sort(key=lambda r: -r["dps"])
hdr = ["config", "n", "failed", "dps", "wspace", "wcap", "kiv dps", "kiv regen", "kiv hull", "kiv route", "turn", "accel", "speed", "guns", "secondary", "score spread"]
print("| " + " | ".join(hdr) + " |"); print("|" + "---|" * len(hdr))
for r in rows:
    cells = []
    for h in hdr:
        v = r[h]
        cells.append(f"{v:+.0%}" if h == "wspace" else f"{v:.0%}" if h == "wcap" else f"{v:+.1f}" if h == "guns"
                     else f"{v:.2f}" if isinstance(v, float) else str(v))
    print("| " + " | ".join(cells) + " |")
