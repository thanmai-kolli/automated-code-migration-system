import subprocess
import tempfile
import os
import shutil


class CValidator:

    def validate(self, code):

        compiler = shutil.which("gcc")

        if not compiler:
            return False, "⚠ gcc not found — compile validation skipped"

        try:
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, "temp.c")

            with open(file_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                [compiler, "-std=c17", file_path],
                capture_output=True,
                text=True
            )

            os.remove(file_path)
            os.rmdir(temp_dir)

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)