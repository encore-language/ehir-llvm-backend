from dataclasses import dataclass
from pathlib import Path

from ehir.backend import EHIR_Backend
from ehir.postprocessor import ProcessedModule

from ehir_llvm_backend.assembler import Assembler
from ehir_llvm_backend.codegen import Codegen
from ehir_llvm_backend.linker import Linker
from ehir_llvm_backend.optimizer import Optimizer


@dataclass
class EHIR_LLVM_Backend(EHIR_Backend):
    def __post_init__(self):
        self._codegen = Codegen()
        self._optimizer = Optimizer()
        self._assembler = Assembler()
        self._linker = Linker()

        self._profile_path = self.target_dir / self.opt_profile
        self._llvm_ir_path = self._profile_path / "llvm"
        self._object_path = self._profile_path / "object"

        self._llvm_ir_path.mkdir(exist_ok=True, parents=True)
        self._object_path.mkdir(exist_ok=True, parents=True)

    def compile_module(self, module: ProcessedModule, name: str) -> Path:
        llvm_ir_raw_module = self._codegen.run(module)
        llvm_ir_opt_module = self._optimizer.run(llvm_ir_raw_module, self.opt_profile)

        with (self._llvm_ir_path / f"{name}.ir").open("w") as f:
            f.write(str(llvm_ir_opt_module))

        object_path = self._assembler.run(llvm_ir_opt_module, self._object_path / f"{name}.o")
        return Linker().run(object_path, self._profile_path / name)
