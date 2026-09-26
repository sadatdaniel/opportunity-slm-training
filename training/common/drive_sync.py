"""Durable Drive sync for training runs (brief 24A).

Attach `DriveSyncCallback` to a Trainer when DRIVE_SYNC_DIR is set: every
checkpoint the Trainer saves is mirrored to Google Drive immediately, with a
`.complete` marker written only after the copy finishes — a VM death mid-copy
can never make a partial checkpoint look valid.

Design choice: model weights + config + tokenizer are synced; optimizer and
scheduler states are not (a 0.6B checkpoint with optimizer states is ~7GB and
would blow typical Drive quotas). Resuming from a weights-only checkpoint
continues training with a fresh optimizer — slightly suboptimal, never fatal.
"""

from __future__ import annotations

import glob
import os
import shutil

from transformers.trainer_callback import TrainerCallback

WEIGHT_FILES = ["model.safetensors", "config.json", "generation_config.json",
                "tokenizer.json", "tokenizer_config.json", "chat_template.jinja",
                "special_tokens_map.json"]


class DriveSyncCallback(TrainerCallback):
    def __init__(self, output_dir: str, drive_root: str, run_name: str):
        self.output_dir = output_dir
        self.dst_root = os.path.join(drive_root, run_name)

    def _newest_checkpoint(self) -> str | None:
        ckpts = sorted(glob.glob(os.path.join(self.output_dir, "checkpoint-*")))
        return ckpts[-1] if ckpts else None

    def on_save(self, args, state, control, **kwargs) -> None:
        src = self._newest_checkpoint()
        if not src:
            return
        name = os.path.basename(src)
        dst = os.path.join(self.dst_root, name)
        if os.path.isdir(os.path.join(dst, ".complete")) or os.path.isfile(os.path.join(dst, ".complete")):
            return  # already synced
        try:
            os.makedirs(dst, exist_ok=True)
            for pattern in WEIGHT_FILES:
                for f in glob.glob(os.path.join(src, pattern)):
                    shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
            # tokenizer subfiles may carry other names; copy any remaining small files
            for f in glob.glob(os.path.join(src, "*")):
                b = os.path.basename(f)
                if b.startswith(("optimizer", "scheduler", "rng_state", "trainer_state")) or b.endswith(".bin"):
                    continue  # optimizer/scheduler state stays VM-local
                if not os.path.isfile(os.path.join(dst, b)) and os.path.isfile(f):
                    shutil.copy2(f, os.path.join(dst, b))
            open(os.path.join(dst, ".complete"), "w").close()
            print(f"[drive-sync] {name} -> {dst}", flush=True)
        except OSError as exc:
            print(f"[drive-sync] FAILED for {name}: {exc}", flush=True)

    def on_train_end(self, args, state, control, **kwargs) -> None:
        self.on_save(args, state, control, **kwargs)
