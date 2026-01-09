import argparse
from pathlib import Path

from ehir import Compiler

from ehir_llvm_backend import EHIR_LLVM_Backend


def main():
    parser = argparse.ArgumentParser(
        prog="ehir-llvm-backend",
    )
    parser.add_argument("input_file", help="Path to the input file", type=Path)

    args = parser.parse_args()
    input_file: Path = args.input_file
    if not input_file.is_absolute():
        input_file = Path().resolve() / input_file

    if not input_file.exists():
        print("Unable to locate this file")
        exit(1)

    with input_file.open("r") as f:
        source_code = f.read()
        name = input_file.stem

    compiler = Compiler()
    ehir_raw_mod = compiler.compile(source_code, name)

    target = EHIR_LLVM_Backend()
    file_path = target.compile(
        ehir_raw_mod,
        input_file.parent / f"{input_file.stem}.o",
        input_file.parent / f"{input_file.stem}.out",
    )
    print("Output file written in:")
    print(file_path)


if __name__ == "__main__":
    main()
