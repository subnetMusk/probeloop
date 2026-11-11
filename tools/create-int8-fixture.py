"""Create a tiny synthetic u8/s8 MatMulInteger graph to check native ONNX CPU kernels."""

from pathlib import Path

import onnx
from onnx import TensorProto, helper

root = Path(__file__).resolve().parents[1]
graph = helper.make_graph(
    [helper.make_node("MatMulInteger", ["x", "weights"], ["result"])],
    "synthetic_int8_kernel",
    [helper.make_tensor_value_info("x", TensorProto.UINT8, [1, 2])],
    [helper.make_tensor_value_info("result", TensorProto.INT32, [1, 2])],
    [helper.make_tensor("weights", TensorProto.INT8, [2, 2], [1, 4, 1, -2])],
)
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
onnx.checker.check_model(model)
onnx.save(model, root / "backend/tests/fixtures/synthetic/installation/matmul-int8.onnx")
