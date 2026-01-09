import argparse
from pathlib import Path

from ehir import Compiler

from ehir_llvm_target import EHIR_LLVM_Target


def main():
    parser = argparse.ArgumentParser(
        prog="ehir-llvm-target-cli",
    )
    parser.add_argument("input_file", help="Path to the input file", type=Path)

    args = parser.parse_args()
    input_file: Path = args.input_file
    if not input_file.is_absolute():
        input_file = Path().resolve() / input_file

    compiler = Compiler()
    ehir_raw_mod = compiler.compile(input_file)

    target = EHIR_LLVM_Target()
    obj_path = target.emit_object_file(
        ehir_raw_mod,
        input_file.parent / f"{input_file.stem}.a",
    )
    print(obj_path)


if __name__ == "__main__":
    main()
