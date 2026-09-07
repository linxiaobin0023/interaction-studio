"""Verify a downloaded Development evidence package without API/database access."""

import argparse
import json
from pathlib import Path

from interaction_studio_api.domain.studio_evidence import verify_evidence

parser = argparse.ArgumentParser()
parser.add_argument("package", type=Path)
args = parser.parse_args()
print(json.dumps(verify_evidence(args.package.read_bytes()), indent=2))
