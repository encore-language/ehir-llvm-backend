from pathlib import Path

from ehir.backend import EHIR_Backend, OptProfile
from ehir.postprocessor import ProcessedModule

from ehir_llvm_backend.assembler import Assembler
from ehir_llvm_backend.codegen import Codegen
from ehir_llvm_backend.linker import Linker
from ehir_llvm_backend.optimizer import Optimizer


class EHIR_LLVM_Backend(EHIR_Backend):
    def __init__(self, output_llvm_ir_path: Path):
        self._codegen = Codegen()
        self._optimizer = Optimizer()
        self._assembler = Assembler()
        self._linker = Linker()

        self._llvm_ir_path = output_llvm_ir_path

    def compile(
        self,
        module: ProcessedModule,
        output_object_path: Path,
        output_file_path: Path,
        opt_level: OptProfile = OptProfile.extreme,
    ) -> Path:
        llvm_ir_raw_module = self._codegen.run(module)
        llvm_ir_opt_module = self._optimizer.run(llvm_ir_raw_module, opt_level)

        with (self._llvm_ir_path / f"{module.name}.ir").open("w") as f:
            f.write(str(llvm_ir_opt_module))

        obj_path = self._assembler.run(llvm_ir_opt_module, output_object_path)
        return self._linker.run(obj_path, output_file_path)
