import subprocess
import tempfile
import os
import shutil


class JavaValidator:

    def validate(self, code):

        if not shutil.which("javac"):
            return False, "⚠ javac not found — compile validation skipped"

        try:
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, "Converted.java")

            with open(file_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                ["javac", file_path],
                capture_output=True,
                text=True,
                timeout=20
            )

            # Clean up
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)