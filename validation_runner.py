#!/usr/bin/env python3

"""
Run repeatable software workloads and capture execution artifacts
"""

import argparse
import csv
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number

def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

"""
Exercise integer arithmetic with deterministic checksum
"""
def cpu_workload(iterations):
    value = 0x12345678

    for _ in range(iterations):
        value = (1664525 * value + 1013904223) & 0xFFFFFFFF

    return {
        "checksum": value,
        "iterations": iterations,
    }

"""
Allocate a buffer, then write and read each byte on every pass
"""
def memory_workload(size_mib, passes):
    size_bytes = size_mib * 1024 * 1024
    buffer = bytearray(size_bytes)
    checksum = 0

    for pass_index in range(passes):
        expected_byte = (pass_index + 1) % 256

        # python-level byte access: not a DRAM-bandwidth benchmark
        for index in range(size_bytes):
            buffer[index] = expected_byte

        observed_sum = sum(buffer)
        expected_sum = expected_byte * size_bytes

        if observed_sum != expected_sum:
            raise RuntimeError(
                f"Buffer check failed on pass {pass_index}: "
                f"expected {expected_sum}, observed {observed_sum}"
            )

        checksum += observed_sum

    return {
        "checksum": checksum,
        "allocated_bytes": size_bytes,
        "passes": passes,
    }

"""
Execute one workload and emit a machine-readable result
"""
def run_worker(args):
    start = time.perf_counter()

    if args.worker == "cpu":
        result = cpu_workload(args.cpu_iterations)
    else:
        result = memory_workload(args.memory_mib, args.memory_passes)

    result.update({
        "workload": args.worker,
        "workload_elapsed_s": time.perf_counter() - start,
    })

    print(json.dumps(result), flush=True)

"""
Check that a successful process also returned a valid result
"""
def validate_worker_result(workload, payload, args):
    if not isinstance(payload, dict):
        raise ValueError("Worker result must be a JSON object")

    if payload.get("workload") != workload:
        raise ValueError("Worker returned the wrong workload name")

    elapsed = payload.get("workload_elapsed_s")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or elapsed <= 0
    ):
        raise ValueError("Worker returned an invalid elapsed time")

    if workload == "cpu":
        if payload.get("iterations") != args.cpu_iterations:
            raise ValueError("Worker returned an unexpected iteration count")

        # independently calculate the expected final value using an affine
        # transform raised to a power in O(log n), rather than rerunning the loop
        multiplier, increment = 1664525, 1013904223
        combined_multiplier, combined_increment = 1, 0
        remaining = args.cpu_iterations
        mask = 0xFFFFFFFF

        while remaining:
            if remaining & 1:
                combined_increment = (
                    multiplier * combined_increment + increment
                ) & mask
                combined_multiplier = (
                    multiplier * combined_multiplier
                ) & mask

            increment = (multiplier * increment + increment) & mask
            multiplier = (multiplier * multiplier) & mask
            remaining >>= 1

        expected = (
            combined_multiplier * 0x12345678 + combined_increment
        ) & mask
    else:
        size_bytes = args.memory_mib * 1024 * 1024

        if (
            payload.get("allocated_bytes") != size_bytes
            or payload.get("passes") != args.memory_passes
        ):
            raise ValueError("Worker returned an unexpected memory config")

        expected = size_bytes * sum(
            (index + 1) % 256 for index in range(args.memory_passes)
        )

    if payload.get("checksum") != expected:
        raise ValueError("worker checksum did not match the expected result")

"""
launch isolated worker, enforce timeout, retain output
"""
def execute_one(workload, run_id, args, output_dir):
    stdout_path = output_dir / f"{run_id}.stdout.txt"
    stderr_path = output_dir / f"{run_id}.stderr.txt"

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker", workload,
        "--cpu-iterations", str(args.cpu_iterations),
        "--memory-mib", str(args.memory_mib),
        "--memory-passes", str(args.memory_passes),
    ]

    row = {
        "run_id": run_id,
        "workload": workload,
        "status": "error",
        "returncode": "",
        "process_elapsed_s": "",
        "workload_elapsed_s": "",
        "checksum": "",
        "error": "",
        "stdout_file": stdout_path.name,
        "stderr_file": stderr_path.name,
    }

    start = time.perf_counter()

    with stdout_path.open("w", encoding="utf-8") as stdout_file, \
            stderr_path.open("w", encoding="utf-8") as stderr_file:
        try:
            completed = subprocess.run(
                command,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=args.timeout,
                check=False,
            )
            row["returncode"] = completed.returncode

            if completed.returncode != 0:
                row["status"] = "failed"
                row["error"] = "Worker exited with a nonzero return code"
            else:
                row["status"] = "completed"

        except subprocess.TimeoutExpired:
            # subprocess.run kills and waits for this worker on timeout
            row["status"] = "timeout"
            row["error"] = f"Worker exceeded {args.timeout} seconds"

        except OSError as exc:
            row["error"] = str(exc)

    row["process_elapsed_s"] = time.perf_counter() - start

    if row["status"] == "completed":
        try:
            payload = json.loads(stdout_path.read_text(encoding="utf-8"))
            validate_worker_result(workload, payload, args)
            row["workload_elapsed_s"] = payload["workload_elapsed_s"]
            row["checksum"] = payload["checksum"]
            row["status"] = "passed"
        except (ValueError, TypeError, KeyError) as exc:
            row["status"] = "invalid_result"
            row["error"] = str(exc)

    return row

