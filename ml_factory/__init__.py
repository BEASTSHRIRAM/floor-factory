"""ML Factory — a sibling factory to THE FLOOR.

Agents propose hypotheses, bid for experiment jobs, run one mutable
training script per experiment inside a fixed compute budget, and are
paid only for metric improvements that an independent Evaluation module
re-computes from raw predictions. Data splits are frozen before any
experiment exists; the holdout is touched exactly once, at campaign
close, by Evaluation only.
"""
