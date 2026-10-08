"""Minimal Inspect task: the three building blocks, nothing else.

Run offline (no API key, no cost) with the built-in mock model:
    uv run inspect eval src/hello_task.py --model mockllm/model

- Dataset: a list of Samples. Each has an `input` (the prompt) and a
  `target` (what the scorer compares against).
- Solver: what happens to each sample. `generate()` just sends the
  prompt to the model and stores its reply.
- Scorer: turns the model's reply into a score. `includes()` checks
  whether the target string appears anywhere in the reply.
"""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes, match
from inspect_ai.solver import generate


@task
def includes_numeric():
    return Task(
        dataset=[
            Sample(input="What is 2 + 2? Answer with a number.", target="4"),
            Sample(input="What is 7 times 2? Answer with a number.", target="4"),
            Sample(input="What is 7 times 5? Answer with a number.", target="4"),
        ],
        solver=generate(),
        scorer=includes(), # this is checking that the model's answer includes the specified target
    )

@task
def includes_text():
    return Task(
        dataset=[
            Sample(input="Who is the author of The Gruffalo?", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name and last name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="Julieta Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="The author of the Gruffalo is Julia Donaldson"),
        ],
        solver=generate(),
        scorer=includes(),
    )

@task
def match_numeric_exact():
    return Task(
        dataset=[
            Sample(input="What is 2 + 2? Answer with a number.", target="4"),
            Sample(input="What is 7 times 2? Answer with a number.", target="4"),
        ],
        solver=generate(),
        scorer=match(location='exact', numeric=True),
    )

@task
def match_numeric_end():
    return Task(
        dataset=[
            Sample(input="What is 2 + 2? Answer with a number.", target="4"),
            Sample(input="What is 7 times 2? Answer with a number.", target="4"),
        ],
        solver=generate(),
        scorer=match(location='end', numeric=True),
    )

@task
def match_text_any():
    return Task(
        dataset=[
            Sample(input="Who is the author of The Gruffalo?", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name and last name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="Julieta Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="The author of the Gruffalo is Julia Donaldson"),
        ],
        solver=generate(),
        scorer=match(location='any'),
    )

@task
def match_text_begin():
    return Task(
        dataset=[
            Sample(input="Who is the author of The Gruffalo?", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo? Give only the name and last name of the writer", target="Julia Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="Julieta Donaldson"),
            Sample(input="Who is the author of The Gruffalo?", target="The author of the Gruffalo is Julia Donaldson"),
        ],
        solver=generate(),
        scorer=match(location='begin'),
    )
