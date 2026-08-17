"""
Cloud Runner Entry Point for NairaLLM V1.5 Semantic Pretraining Pilot.
"""

from __future__ import annotations

import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.training.scripts.run_semantic_pilot import main

if __name__ == "__main__":
    main()
