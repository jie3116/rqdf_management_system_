from app import create_app, db
from app.models import User, UserRole
import os

app = create_app()

# Shell context processor agar mudah testing di terminal
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'UserRole': UserRole}

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=8000, debug=debug_mode)