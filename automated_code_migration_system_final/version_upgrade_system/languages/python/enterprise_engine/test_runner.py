import traceback


class TestRunner:

    def run(self, code):

        namespace = {}

        try:
            exec(code, namespace)
            return {
                "test_success": True,
                "test_error": None
            }

        except Exception as e:
            return {
                "test_success": False,
                "test_error": traceback.format_exc()
            }
