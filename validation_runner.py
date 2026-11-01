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