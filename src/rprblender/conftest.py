"""
configuration for pytest-based tests
"""
import sys
import pytest
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption('--keep-blender-running', action='store_true')
    parser.addoption('-E', "--render-check-generate-missing-expected-image", action='store_true')
    parser.addoption('-R', "--render-check-regenerate-expected-image", action='store_true')
    parser.addoption('-Q', '--render-quickest', action='store_true', help='render test the fast way, minimum iterations, no image comparison')
    parser.addoption('--perf', action='store_true', help='run tests that are used for performance profiling')
    parser.addoption("--enable-cpu", action='store_true')
    parser.addoption("--enable-trace", action='store_true')
