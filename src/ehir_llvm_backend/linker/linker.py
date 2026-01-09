import subprocess
from pathlib import Path


class Linker:
    def run(self, obj_file_path: Path, output_file_path: Path) -> Path:
        cmd = ["clang", obj_file_path, "-o", output_file_path, "-lc", "-lm", "-lpthread", "-ldl"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Link error: {result.stderr}")

        return output_file_path
