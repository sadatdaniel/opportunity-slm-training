# Learning Notes

Educational notes explaining the ML concepts this project exercises, updated
with real experiment numbers as they become available (build brief section 37).

Planned sections:

- Supervised fine-tuning; completion-only loss
- Tokenizer length; why 600 input words + instructions + 150 output words can
  overflow a 1,024-token context
- Epochs, training vs. validation loss, overfitting, learning rate
- Full fine-tuning vs. LoRA/PEFT for a ~100M parameter model
- Sequence classification vs. generation; classification heads, logits, softmax
- Confidence and calibration: ECE, Brier score, temperature scaling
- Train/validation/test separation, data leakage, duplicate-group aware splits
- Dataset quality tiers: gold / silver / quarantine
- One-forward-pass System-One inference (no autoregressive answer generation)
