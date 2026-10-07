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
from inspect_ai.scorer import includes
from inspect_ai.solver import generate


@task
def hello():
    return Task(
        dataset=[
            Sample(input="What is 2 + 2? Answer with a number.", target="4"),
            Sample(input="What is the capital of France? One word.", target="Paris"),
            Sample(input="Reverse the string 'abc'. Answer only the result.", target="cba"),
        ],
        solver=generate(),
        scorer=includes(),
    )
