import subprocess
import tempfile
import os
import shutil


class CppValidator:

    def validate(self, code):

        compiler = shutil.which("g++") or shutil.which("clang++")

        if not compiler:
            return False, "⚠ C++ compiler not found — compile validation skipped"

        temp_dir = tempfile.mkdtemp()

        try:
            file_path = os.path.join(temp_dir, "temp.cpp")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                # Without -o the linker drops a.out/a.exe into the server's
                # working directory, so concurrent requests overwrite one
                # another and a locked file reads back as a compile failure.
                [compiler, "-std=c++17", file_path, "-o", os.path.join(temp_dir, "a.out")],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=temp_dir
            )

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)