#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Use virtualenv pytest
PYTEST="./venv/bin/pytest"
export PYTHONPATH=$PYTHONPATH:.

echo "=== Running Serial Tests Baseline ==="
time $PYTEST -q --maxfail=1 --durations=10

echo ""
echo "=== Running Parallel Tests (auto workers) ==="
time $PYTEST -q -n auto --dist=loadscope --maxfail=1 --durations=10

echo ""
echo "=== Running Parallel Tests (4 workers) ==="
time $PYTEST -q -n 4 --dist=loadscope --maxfail=1 --durations=10
