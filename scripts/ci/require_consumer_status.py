"""Require the independently verified private consumer status before publication."""

from __future__ import annotations

import json
import os
import subprocess
from urllib.request import Request, urlopen

source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
repository = os.environ["GITHUB_REPOSITORY"]
request = Request(
    f"https://api.github.com/repos/{repository}/commits/{source}/status",
    headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)
with urlopen(request, timeout=30) as response:
    payload = json.load(response)
statuses = [item for item in payload["statuses"] if item["context"] == "meander-compatibility"]
if not statuses or statuses[0]["state"] != "success":
    raise SystemExit(f"Missing successful meander-compatibility check for {source}")
print(f"Private consumer acceptance recorded for {source}")
