#!/usr/bin/env bash
# Reproduce all STRIVE results and figures.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
cd code
python ml_experiments.py | tee ../results/ml_log.txt
python agent_sim.py
python fig1_arch.py; python fig2_sequence.py; python fig_results.py
cd ../contracts && npm ci && npx hardhat test | tee ../results/security_tests.txt
npx hardhat run scripts/bench.js
