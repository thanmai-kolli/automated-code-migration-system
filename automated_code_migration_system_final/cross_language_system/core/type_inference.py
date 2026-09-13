from core.ml_type_predictor import MLTypePredictor

class TypeInferenceEngine:

    def __init__(self):
        self.ml_predictor = MLTypePredictor()
        self.variable_usage = {}   # if you're tracking usage

    def _get_variable_features(self, value):

        # This assumes you're tracking variable usage somewhere
        # You must pass variable name or context

        if hasattr(value, "name") and value.name in self.variable_usage:
            usage = self.variable_usage[value.name]

            return {
                "num_append_int": usage.get("append_int", 0),
                "num_append_str": usage.get("append_str", 0),
                "used_in_arithmetic": usage.get("arithmetic", 0),
                "used_in_loop": usage.get("loop", 0),
            }

        return None

    def infer(self, expr, var_name=None):

        if expr is None:
            return "void"

        # Constant values
        if hasattr(expr, "value"):

            if isinstance(expr.value, bool):
                return "boolean"

            if isinstance(expr.value, int):
                return "int"

            if isinstance(expr.value, float):
                return "double"

            if isinstance(expr.value, str):
                return "String"

        # Binary operations
        if expr.__class__.__name__ == "BinaryOp":

            left_type = self.infer(expr.left)
            right_type = self.infer(expr.right)

            if left_type == "double" or right_type == "double":
                return "double"

            if left_type == "String" or right_type == "String":
                return "string"

            return "int"

        # Boolean operations
        if expr.__class__.__name__ == "BooleanOp":
            return "bool"

        # Arrays
        if expr.__class__.__name__ == "ArrayLiteral":

            if not expr.elements:

                # 🔹 Try ML refinement if variable context exists
                if var_name and hasattr(self, "variable_usage"):

                    usage = self.variable_usage.get(var_name)

                    if usage:
                        features = {
                            "num_append_int": usage.get("append_int", 0),
                            "num_append_str": usage.get("append_str", 0),
                            "used_in_arithmetic": usage.get("arithmetic", 0),
                            "used_in_loop": usage.get("loop", 0),
                        }

                        predicted = self.ml_predictor.predict(features)

                        if predicted:
                            return predicted

                # 🔹 Fallback
                return "List<Object>"

            element_type = self.infer(expr.elements[0])
            return f"List<{element_type}>"

        return "Object"