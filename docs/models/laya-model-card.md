---
license: apache-2.0
language:
- it
pipeline_tag: text-classification
base_model: convaiinnovations/laya-multilingual
tags:
- onnx
- onnxruntime
- modernbert
- probeloop
- stated-limits
- experimental
model-index:
- name: ProbeLoop Laya stated-limit classifier (provisional)
  results: []
---

# ProbeLoop Laya stated-limit classifier

**Provisional checkpoint, trained on 2026-11-10.** This is an experimental fine-tuning of
[Laya multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) for one narrow task:
identifying sentences in which an interview candidate explicitly states that they do not know,
do not remember, or lack the experience asked about. Future fine-tuning may replace this version.
Pin a commit revision and verify the checksums in `manifest.json` when installing it.

It does not choose interview objectives, assess candidate competence, or decide interview moves.
It does not generate text. Limits of a method, missing data and ordinary hedges are negative
examples; a candidate's own stated knowledge or experience limit is positive.

## Files and architecture

- `model.safetensors`: the **fine-tuned** encoder and two-class linear head, in float32.
- `encoder/config.json`: the encoder's original ModernBERT configuration.
- `limits-int8.onnx`: the deployment export, with dynamic int8 weight quantization (308 MB).
- `tokenizer/`: the tokenizer used during training and deployment.
- `config.json` and `manifest.json`: task configuration, provenance, sizes and SHA-256 checksums.

The custom classifier uses `ModernBertModel`, attention-mask-weighted mean pooling over the last
hidden state, and `Linear(hidden_size, 2)`. State-dict keys start with `encoder.` and `head.`.
These are custom task weights, not the upstream Laya decision heads or a standard Transformers
sequence-classification checkpoint. Do not load them through an unrelated automatic pipeline.

## ONNX inference

Only `onnxruntime`, `tokenizers` and NumPy are required. No torch or Laya SDK is needed.
The example runs on CPU and returns the probability for a **single answer sentence**.

```python
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

tokenizer = Tokenizer.from_file("tokenizer/tokenizer.json")
tokenizer.enable_truncation(max_length=192, strategy="longest_first")
tokenizer.enable_padding()
options = ort.SessionOptions()
options.intra_op_num_threads = 2
options.inter_op_num_threads = 1
options.add_session_config_entry("session.intra_op.allow_spinning", "0")
session = ort.InferenceSession(
    "limits-int8.onnx", sess_options=options, providers=["CPUExecutionProvider"]
)
question = "Hai mai gestito un progetto simile?"
sentence = "Non ho ancora avuto questa esperienza."
encoded = tokenizer.encode_batch([(question[-300:], sentence)])
feeds = {
    "input_ids": np.asarray([e.ids for e in encoded], dtype=np.int64),
    "attention_mask": np.asarray([e.attention_mask for e in encoded], dtype=np.int64),
}
logits = session.run(None, feeds)[0]
scores = np.exp(logits - logits.max(axis=1, keepdims=True))
probability = float((scores[:, 1] / scores.sum(axis=1))[0])
print(probability, probability >= 0.5)
```

For an answer, split with `re.split(r"(?<=[.!?;])\s+", answer)`, strip each sentence and discard
sentences with at most three characters. Pair each sentence with the last 300 **characters** of
the interviewer's question. Tokenize pairs with `longest_first` truncation to 192 tokens and
padding. Apply softmax and select sentences whose class-1 probability is at least 0.5.
Preserve the original sentence text. The threshold is not a calibrated confidence guarantee.

## Training and evaluation

Training used 2,549 synthetic Italian sentence pairs, including 362 positive examples, from
synthetic interview development conversations labelled by Claude. There are five profession
groups; evaluation leaves one entire group out at a time. The final deployed checkpoint was
trained on all rows, for three epochs, with AdamW, learning rate 3e-5, weight decay 0.01, batch
size 16, class-weighted cross entropy and seed 0. GPU training used mixed precision.

At threshold 0.5, the cross-profession pilot found 288/294 answers containing a stated limit
(98.0%) and flagged 8/312 answers without one (2.6%). Sentence precision was approximately 0.91
and recall 0.98. This is a synthetic development evaluation, **not** an independent test of real
interviews. The reported metrics concern held-out-group models, not a fresh evaluation of the
final checkpoint on unseen data. The int8 and float32 ONNX exports made the same decisions on
all 2,549 development sentences; that does not establish equivalence on other inputs.

The synthetic examples, prompts, label decisions and threshold selection may introduce biases.
Italian spoken transcripts, recognition errors, unfamiliar professions, negation and implicit
limits need independent validation. Other languages supported by the base encoder were not
validated for this fine-tuning. Do not use these scores to grade, rank or make employment
decisions about people.

## Attribution

Fine-tuned for ProbeLoop by submsk. Based on `convaiinnovations/laya-multilingual`, whose
multilingual encoder is mmBERT-base; retain the upstream attribution and Apache-2.0 licence.
Model weights and runtime exports are distributed under Apache-2.0. No real CVs, recordings,
transcripts, personal data or authentication material are included in this release.
