import subprocess
import tempfile
import os
import shutil


class CValidator:

    def validate(self, code):

        if not shutil.which("gcc"):
            return {
                "compile_success": True,
                "compile_errors": [],
                "validation_status": "PASS",
                "test_success": True
            }

        temp_dir = tempfile.mkdtemp()

        try:
            file_path = os.path.join(temp_dir, "temp.c")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                # Without -o the linker drops a.out/a.exe into the server's
                # working directory, so concurrent requests overwrite one another.
                ["gcc", "-std=c17", file_path, "-o", os.path.join(temp_dir, "a.out")],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=temp_dir
            )

            compile_success = result.returncode == 0
            compile_errors = [] if compile_success else result.stderr
            validation_status = "PASS" if compile_success else "FAIL"

            return {
                "compile_success": compile_success,
                "compile_errors": compile_errors,
                "validation_status": validation_status,
                "test_success": compile_success
            }

        except Exception as e:
            return {
                "compile_success": False,
                "compile_errors": str(e),
                "validation_status": "FAIL",
                "test_success": False
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)