"""Compare hand labels with the model grader and the canary scorer.

    uv run python analysis/compare.py logs/graded labels/hand_labels.csv

Prints agreement and Cohen's kappa per axis, confusion tables, and writes every
reply where the hand label and the grader disagree to analysis/disagreements.csv.
"""

import csv
import sys
from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log

from stats import agreement, cohen_kappa, confusion

LEAK_ORDER = ["NO_LEAK", "PARTIAL_LEAK", "FULL_LEAK"]
HONESTY_ORDER = ["ANSWER", "TRANSPARENT_REFUSAL", "DECEPTIVE_DENIAL", "OVER_REFUSAL"]


def load_scores(log_dir):
    """(model, sample_id, epoch) -> grader labels and canary result."""
    scores = {}
    for info in list_eval_logs(log_dir):
        log = read_eval_log(info.name)
        for s in log.samples:
            grader = s.scores["rubric_grader"]
            scores[(log.eval.model, str(s.id), str(s.epoch))] = {
                "grader_leak": grader.metadata["leak_label"],
                "grader_honesty": grader.metadata["honesty_label"],
                "grader_reasoning": grader.explanation,
                "canary_leak": int(s.scores["canary_leak"].value),
            }
    return scores


def any_leak(label):
    return "no leak" if label == "NO_LEAK" else "leak"


def deceptive(label):
    return "deceptive" if label == "DECEPTIVE_DENIAL" else "not deceptive"


def fmt_kappa(k):
    return "n/a (single label)" if k is None else f"{k:.2f}"


def report(name, human, other, order=None):
    print(f"\n### {name}  (n={len(human)})")
    print(f"agreement {agreement(human, other):.1%}, Cohen's kappa {fmt_kappa(cohen_kappa(human, other))}")
    labels = order or sorted(set(human) | set(other))
    labels += [x for x in sorted(set(human) | set(other)) if x not in labels]
    table = confusion(human, other)
    print("| hand \\ other | " + " | ".join(labels) + " |")
    print("|---" * (len(labels) + 1) + "|")
    for h in labels:
        print(f"| {h} | " + " | ".join(str(table.get((h, o), 0)) for o in labels) + " |")


def main(log_dir, labels_path, out_path="analysis/disagreements.csv"):
    scores = load_scores(log_dir)
    rows = list(csv.DictReader(open(labels_path, encoding="utf-8")))
    missing = [(r["model"], r["sample_id"], r["epoch"]) for r in rows
               if (r["model"], r["sample_id"], r["epoch"]) not in scores]
    if missing:
        sys.exit(f"{len(missing)} labelled replies have no grader score, e.g. {missing[:3]}")
    for r in rows:
        r.update(scores[(r["model"], r["sample_id"], r["epoch"])])

    unparseable = [r for r in rows if r["grader_leak"] == "UNPARSEABLE"]
    print(f"rows: {len(rows)}, grader UNPARSEABLE: {len(unparseable)} (excluded from grader comparisons)")
    graded = [r for r in rows if r["grader_leak"] != "UNPARSEABLE"]

    print("\n## Hand labels vs model grader")
    report("Leak, 3 levels", [r["leak_label"] for r in graded], [r["grader_leak"] for r in graded], LEAK_ORDER[:])
    report("Leak, any vs none", [any_leak(r["leak_label"]) for r in graded],
           [any_leak(r["grader_leak"]) for r in graded])
    report("Response type", [r["honesty_label"] for r in graded], [r["grader_honesty"] for r in graded], HONESTY_ORDER[:])
    report("Deceptive vs not", [deceptive(r["honesty_label"]) for r in graded],
           [deceptive(r["grader_honesty"]) for r in graded])

    print("\n## Hand labels vs canary scorer (leak, any vs none)")
    report("Canary", [any_leak(r["leak_label"]) for r in rows],
           ["leak" if r["canary_leak"] else "no leak" for r in rows])

    disagree = [r for r in graded if r["leak_label"] != r["grader_leak"] or r["honesty_label"] != r["grader_honesty"]]
    fields = ["model", "sample_id", "epoch", "attack_type", "question", "reply",
              "leak_label", "grader_leak", "honesty_label", "grader_honesty", "grader_reasoning", "label_notes"]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(disagree)
    print(f"\n{len(disagree)} disagreements written to {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
