# Workload Validation Runner

An early-stage Python test-automation project for running controlled
CPU-oriented and memory-oriented software workloads.

## Current capabilities

- Configurable workload sizes and repetition counts
- Separate worker processes with execution timeouts
- Deterministic result checks
- CSV results and JSON environment metadata
- Per-run stdout and stderr artifacts
- Timing summaries and unsuccessful-run counts

## Requirements

Python 3.9 or newer. No third-party packages required.

## Usage

python3 validation_runner.py --runs 5

## Measurement limitations

The workloads execute through Python. They are not native CPU-throughput,
DRAM-bandwidth, cache-coherence, or silicon-validation benchmarks.

The runner does not currently collect power, temperature, frequency,
hardware performance counters, or CPU affinity.

Results depend on the machine, Python version, operating system,
background activity, and thermal conditions. Timings from different
configurations should not be treated as directly comparable.

## Planned work

- Automated tests for result validation and failure handling
- Optional Linux telemetry collection
- Controlled baseline comparison
- Native workloads for more targeted systems experiments