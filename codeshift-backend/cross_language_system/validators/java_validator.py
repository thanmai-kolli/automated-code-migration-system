import subprocess
import tempfile
import os
import shutil


class JavaValidator:

    def validate(self, code):

        if not shutil.which("javac"):
            return False, "⚠ javac not found — compile validation skipped"

        temp_dir = tempfile.mkdtemp()

        try:
            file_path = os.path.join(temp_dir, "Converted.java")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                ["javac", "-encoding", "UTF-8", file_path],
                capture_output=True,
                text=True,
                timeout=20
            )

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)