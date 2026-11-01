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

