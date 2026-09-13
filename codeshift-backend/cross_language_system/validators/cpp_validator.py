import subprocess
import tempfile
import os
import shutil


class CppValidator:

    def validate(self, code):

        compiler = shutil.which("g++") or shutil.which("clang++")

        if not compiler:
            return False, "⚠ C++ compiler not found — compile validation skipped"

        try:
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, "temp.cpp")

            with open(file_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                [compiler, "-std=c++17", file_path],
                capture_output=True,
                text=True,
                timeout=20
            )

            os.remove(file_path)
            os.rmdir(temp_dir)

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)