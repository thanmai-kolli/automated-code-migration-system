from flask import Blueprint, request, jsonify, Response
from werkzeug.exceptions import HTTPException
import traceback
import json

from cross_language_system.main_cross import run_cross_language_api
from cross_language_system.core.language_normalizer import LanguageNormalizer

cross_language_bp = Blueprint("cross_language", __name__)


@cross_language_bp.route("/cross-language", methods=["POST"])
def cross_language():

    try:
        data = request.get_json(force=True)

        code = data.get("code")
        source = LanguageNormalizer.normalize(data.get("source_language"))
        target = LanguageNormalizer.normalize(data.get("target_language"))

        if not code:
            return jsonify({"success": False, "error": "Code is required"}), 400

        if not source or not target:
            return jsonify({
                "success": False,
                "error": "Both source_language and target_language are required"
            }), 400

        result = run_cross_language_api(
            code=code,
            source=source,
            target=target
        )

        if result is None:
            return jsonify({
                "success": False,
                "error": "Engine returned no result."
            }), 500

        if isinstance(result, dict) and "error" in result:
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 400

        # ✅ SUCCESS RESPONSE
        return jsonify({
            "success": True,
            "data": result
        })

    except HTTPException:
        raise

    except Exception:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Internal Server Error"
        }), 500