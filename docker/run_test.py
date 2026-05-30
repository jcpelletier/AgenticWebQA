#!/usr/bin/env python3
"""Deprecated shim — use `agenticwebqa-run-test` instead.

Kept so existing CI workflows and Docker images continue to work.
The real implementation lives at `agenticwebqa.run_test`.
"""
from agenticwebqa.run_test import main

if __name__ == "__main__":
    main()
