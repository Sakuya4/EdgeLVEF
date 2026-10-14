# EdgeLVEF video model

This package contains the PLAX-only Teacher–Student method, architecture source, training scripts and aggregate statistics.

We train a two-model R(2+1)D-18 Teacher ensemble and transfer its EF predictions and video representation to a compact Student. The selected Student uses MobileNetV3-Large, temporal shift and residual depthwise temporal convolutions. It contains 3,212,755 parameters and operates independently of the Teacher at inference.

## Read the method

- [Method](METHOD.md): model design, distillation and training settings.
- [Results](RESULTS.md): six-backbone comparison and EF error analysis.
- [Model specification](MODEL_CARD.md): task and components.
- [Teacher](TEACHER_MODEL_CARD.md) and [Student](STUDENT_MODEL_CARD.md): network details.
- [Reproduction](REPRODUCIBILITY.md): authorized inputs and commands.
- [References](REFERENCES.md): research foundations.
- [Manuscript prompt](PAPER_WRITING_PROMPT.md): instructions for writing a report from this package.

## Inspect the architecture

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/train_teacher.py --help
python scripts/train_student.py --help
```

The architecture tests instantiate models without downloading pretrained weights. Training uses locally authorized data. This public package includes architecture and aggregate outputs; trained LVEF weights, source images and individual records remain outside Git.
