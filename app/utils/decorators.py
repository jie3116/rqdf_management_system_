from functools import wraps
from flask import request, redirect, url_for
from app.utils.security import is_safe_url

def safe_redirect(default_endpoint: str):
    """
    Decorator untuk redirect aman menggunakan parameter ?next=
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            # hanya proses jika view mengembalikan redirect
            if response is not None:
                return response

            next_page = request.args.get("next")

            if is_safe_url(next_page):
                return redirect(next_page)

            return redirect(url_for(default_endpoint))

        return wrapped_view
    return decorator
