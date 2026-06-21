#!/usr/bin/env python3
"""Compatibility wrapper for the renamed dkb_to_ynab4 module."""

from dkb_to_ynab4 import *  # noqa: F403
from dkb_to_ynab4 import main


if __name__ == "__main__":
    main()
