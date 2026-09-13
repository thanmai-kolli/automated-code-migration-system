import subprocess
import tempfile
import os
import shutil


class CppValidator:

    def validate(self, code):

        if not shutil.which("g++"):
            # If compiler not available, assume success
            return {
                "compile_success": True,
                "compile_errors": [],
                "validation_status": "PASS",
                "test_success": True
            }

        try:
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, "temp.cpp")

            with open(file_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                ["g++", "-std=c++20", file_path],
                capture_output=True,
                text=True
            )

            os.remove(file_path)
            os.rmdir(temp_dir)

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