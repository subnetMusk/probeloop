"""A synthetic quantised kernel checks the runtime without distributing trained weights."""

from pathlib import Path

import numpy as np
import onnxruntime as ort


def test_synthetic_int8_cpu_kernel() -> None:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    path = Path(__file__).parents[1] / "fixtures/synthetic/installation/matmul-int8.onnx"
    session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
    result = session.run(None, {"x": np.asarray([[2, 3]], dtype=np.uint8)})[0]
    np.testing.assert_array_equal(result, [[5, 2]])
