#!/usr/bin/env python3
"""Compatibility module for importing setup-wizard.py as setup_wizard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_WIZARD_PATH = Path(__file__).with_name("setup-wizard.py")
_SPEC = importlib.util.spec_from_file_location("setup_wizard_impl", _WIZARD_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"unable to load setup wizard module: {_WIZARD_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

detect_primary_model = _MODULE.detect_primary_model

__all__ = ["detect_primary_model"]
