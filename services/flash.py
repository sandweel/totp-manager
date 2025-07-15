from fastapi import Request

def flash(request: Request, message: str, category: str = "info"):
    request.session["_flash"] = {"message": message, "category": category}

def get_flashed_message(request: Request):
    return request.session.pop("_flash", None)
