#!/usr/bin/env python3
"""Run FabInventory web application"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.app import main

if __name__ == '__main__':
    main()