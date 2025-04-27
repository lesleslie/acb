#!/usr/bin/env python3
"""Run tests directly with pytest."""

import subprocess
import sys

result = subprocess.run(["python", "-m", "pytest"] + sys.argv[1:], check=False)
sys.exit(result.returncode)
