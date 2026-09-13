import subprocess
import tempfile
import os
import shutil


class CValidator:

    def validate(self, code):

        compiler = shutil.which("gcc")

        if not compiler:
            return False, "⚠ gcc not found — compile validation skipped"

        temp_dir = tempfile.mkdtemp()

        try:
            file_path = os.path.join(temp_dir, "temp.c")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                # Without -o the linker drops a.out/a.exe into the server's
                # working directory, so concurrent requests overwrite one
                # another and a locked file reads back as a compile failure.
                [compiler, "-std=c17", file_path, "-o", os.path.join(temp_dir, "a.out")],
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