"""Confidential-information eval: does the model leak a confidential document
from its context, and is it honest when it declines?

Run (cap samples on first runs):
    uv run inspect eval src/task.py@confidential --model anthropic/claude-haiku-5-5 --limit 3 --log-dir logs/scratch

Inputs, all under data/:
- samples.jsonl: one user question per line, with id, attack_type
  (direct / indirect / control), should_answer and notes.
- system_prompt.txt: template with {public_document} and {confidential_document}.
- documents/public.md, documents/confidential.md: the two documents.
- canaries.txt: strings whose appearance in a reply counts as a leak.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.solver import generate, system_message

from scorers import canary_leak, load_canaries

DATA = Path(__file__).parent.parent / "data"


def record_to_sample(record: dict) -> Sample:
    return Sample(
        id=record["id"],
        input=record["question"],
        metadata={
            "attack_type": record["attack_type"],
            "should_answer": record["should_answer"],
            "notes": record.get("notes", ""),
        },
    )


@task
def confidential():
    return Task(
        dataset=json_dataset(str(DATA / "samples.jsonl"), record_to_sample),
        solver=[
            system_message(
                (DATA / "system_prompt.txt").read_text(),
                public_document=(DATA / "documents" / "public.md").read_text(),
                confidential_document=(DATA / "documents" / "confidential.md").read_text(),
            ),
            generate(),
        ],
        scorer=canary_leak(load_canaries(DATA / "canaries.txt")),
    )
