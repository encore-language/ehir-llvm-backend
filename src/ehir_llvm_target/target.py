from pathlib import Path

from ehir.postprocessor import ProcessedModule

from ehir_llvm_target.assembler import Assembler
from ehir_llvm_target.codegen import Codegen
from ehir_llvm_target.optimizer import Optimizer, OptLevel


class EHIR_LLVM_Target:
    def __init__(self):
        self._codegen = Codegen()
        self._optimizer = Optimizer()
        self._assembler = Assembler()

    def emit_object_file(
        self, module: ProcessedModule, object_output_path: Path, opt_level: OptLevel = OptLevel.O1
    ) -> Path:
        llvm_ir_raw_module = self._codegen.run(module)
        llvm_ir_opt_module = self._optimizer.run(llvm_ir_raw_module, opt_level)
        obj_path = self._assembler.run(llvm_ir_opt_module, object_output_path)
        return obj_path
