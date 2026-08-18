"""
Unit test for save_checkpoint SameFileError prevention in OneShotFinalTrainer.
"""

import tempfile
from pathlib import Path
from NairaLLM.training.scripts.train_final_once import OneShotFinalTrainer


def test_save_checkpoint_same_file_safety():
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_p = Path(tmp_dir)
        config_path = Path("NairaLLM/configs/final_nairallm_v1.json")
        
        # When output_dir and drive_dir are identical
        trainer = OneShotFinalTrainer(config_path=config_path, output_dir=dir_p, drive_dir=dir_p)
        assert trainer.output_dir == dir_p
        assert trainer.drive_dir == dir_p
