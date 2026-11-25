"""Campaign store: a directory of JSON artefacts plus an append-only log.

Layout of a campaign directory:

    campaigns/<campaign-id>/
        charter.json          the human-signed campaign charter (baseline frozen in)
        dataset/              the frozen dataset (read-only after freeze)
            X.npy, y.npy, splits.json, manifest.json
        log.jsonl             append-only event log (one JSON object per line)
        hypotheses.json       pre-registered hypotheses (written before any run)
        experiments/<exp-id>/ one directory per experiment run
        model_card.md         the campaign report (Markdown)
        model_card.json       the campaign report (machine-readable)

The log is the audit trail: every state change in a campaign is an
event in log.jsonl, appended, never edited.
"""
from __future__ import annotations

import json
import os
import time


class CampaignStore:
    def __init__(self, campaign_dir: str):
        self.dir = campaign_dir
        os.makedirs(self.dir, exist_ok=True)
        self.log_path = os.path.join(self.dir, "log.jsonl")

    # -- append-only log -------------------------------------------------
    def log(self, event: str, **fields) -> dict:
        record = {"ts": round(time.time(), 3), "event": event}
        record.update(fields)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def read_log(self) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        out = []
        with open(self.log_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    # -- JSON artefacts ----------------------------------------------------
    def write_json(self, name: str, obj) -> str:
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
        return path

    def read_json(self, name: str):
        with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
            return json.load(fh)

    def path(self, *parts) -> str:
        return os.path.join(self.dir, *parts)
