# app/routes.py

from flask import current_app as app

@app.route('/')
def test_page():
    return "<h1>Ini dari file routes.py!</h1>"