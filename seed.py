
from app import create_app, db
from app.models import User, UserRole, Staff
from werkzeug.security import generate_password_hash

def create_admin():
    app = create_app()
    with app.app_context():
        # Cek apakah admin sudah ada
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user sudah ada!")
            return

        # Buat user admin
        admin_user = User(
            username='admin',
            email='admin@sekolah.com',
            password_hash=generate_password_hash('admin123'),
            role=UserRole.ADMIN,
            must_change_password=False
        )

        db.session.add(admin_user)
        db.session.flush()

        # Buat profile staff
        staff_profile = Staff(
            user_id=admin_user.id,
            full_name='Administrator System',
            position='System Administrator'
        )

        db.session.add(staff_profile)
        db.session.commit()

        print("✅ Admin user berhasil dibuat!")
        print("Username: admin")
        print("Password: admin123")
        print("Role: ADMIN")

if __name__ == '__main__':
    create_admin()