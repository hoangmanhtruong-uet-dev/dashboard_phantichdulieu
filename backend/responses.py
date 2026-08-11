from typing import Any, Optional


def success_response(
    data: Any = None, *, meta: Optional[dict] = None, legacy: Optional[dict] = None
) -> dict:
    """Build the v1 response envelope while allowing temporary legacy fields."""
    response = {"success": True, "data": data}
    if meta is not None:
        response["meta"] = meta
    if legacy:
        response.update(legacy)
    return response


def error_response(code: str, message: str, *, details: Any = None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}
