"""Build a hand-labelling sheet from Inspect logs: one row per model reply.

    uv run python analysis/make_label_sheet.py logs/final labels/hand_labels.csv

Fills in everything known from the logs (question, reply, canary scorer result)
and leaves leak_label, honesty_label and label_notes empty for hand labelling.
Refuses to overwrite an existing sheet, so labels already written are never lost.
"""

import csv
import sys
from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log

COLUMNS = [
    "sample_id", "model", "epoch", "attack_type", "should_answer",
    "question", "reply", "canary_leak", "canary_facts_found",
    "leak_label", "honesty_label", "label_notes",
]


def rows_from_log(path):
    log = read_eval_log(path)
    for s in log.samples:
        score = s.scores["canary_leak"]
        yield {
            "sample_id": s.id,
            "model": log.eval.model,
            "epoch": s.epoch,
            "attack_type": s.metadata["attack_type"],
            "should_answer": s.metadata["should_answer"],
            "question": s.input,
            "reply": s.output.completion,
            "canary_leak": score.value,
            "canary_facts_found": "; ".join(score.metadata.get("facts_found", [])),
            "leak_label": "",
            "honesty_label": "",
            "label_notes": "",
        }


def main(log_dir, out_path):
    out = Path(out_path)
    if out.exists():
        sys.exit(f"{out} already exists; not overwriting labels.")
    rows = [row for info in list_eval_logs(log_dir) for row in rows_from_log(info.name)]
    rows.sort(key=lambda r: (r["model"], r["sample_id"], r["epoch"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
