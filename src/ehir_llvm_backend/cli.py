import argparse
from pathlib import Path

from ehir.compiler import EHIR_ProjectCompiler, Target
from ehir.frontend.builtin import EHIR_DirectFrontend

from ehir_llvm_backend import EHIR_LLVM_Backend

AVAILABLE_PROFILES = {
    "debug": EHIR_LLVM_Backend.OptProfile.debug,
    "release": EHIR_LLVM_Backend.OptProfile.release,
    "extreme": EHIR_LLVM_Backend.OptProfile.extreme,
}


def main():
    parser = argparse.ArgumentParser(
        prog="ehir-llvm-backend",
    )
    parser.add_argument("input_file", help="Path to the input file", type=Path)
    parser.add_argument("--profile", default="debug", choices=AVAILABLE_PROFILES.keys(), help="Optimization profile")

    args = parser.parse_args()

    input_file: Path = args.input_file
    if not input_file.is_absolute():
        input_file = Path().resolve() / input_file

    if not input_file.exists():
        print("Unable to locate this file")
        exit(1)

    opt_profile = AVAILABLE_PROFILES[args.profile]
    compiler = EHIR_ProjectCompiler(
        frontend=EHIR_DirectFrontend(),
        backend=EHIR_LLVM_Backend(target_dir=input_file.parent / "target", opt_profile=opt_profile),
    )
    compiler.add_target_to_build(Target(input_file, type=Target.TargetType.BINARY))
    compiler.compile_all_targets()


if __name__ == "__main__":
    main()
