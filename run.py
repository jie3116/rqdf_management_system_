from app import create_app, db
from app.models import User, UserRole

app = create_app()

# Shell context processor agar mudah testing di terminal
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'UserRole': UserRole}

if __name__ == '__main__':
    app.run(debug=True)