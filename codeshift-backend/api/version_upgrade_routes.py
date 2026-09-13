from flask import Blueprint, request, jsonify
from werkzeug.exceptions import HTTPException
import traceback
from version_upgrade_system.main import run_version_upgrade_api

version_upgrade_bp = Blueprint("version_upgrade", __name__)


@version_upgrade_bp.route("/version-upgrade", methods=["POST"])
def version_upgrade():

    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "Invalid JSON body"}), 400

        code = data.get("code")
        language = data.get("language")
        
        if not code:
            return jsonify({"error": "Code is required"}), 400

        if not language:
            return jsonify({"error": "Language is required"}), 400

        result = run_version_upgrade_api(
            code=code,
            language=language,
            test_cases=data.get("test_cases")
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify({
            "success": True,
            "data": result
        })

    except HTTPException:
        raise

    except Exception:
        traceback.print_exc()
        return jsonify({
            "error": "Internal Server Error"
        }), 500