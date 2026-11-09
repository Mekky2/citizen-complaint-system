from getpass import getpass
from app.db import SessionLocal
from app.models.identity import User, Role, UserRole
from app.security.hashing import hash_password

db = SessionLocal()

try:
    existing = (
        db.query(User)
        .join(UserRole)
        .join(Role)
        .filter(Role.name == "admin")
        .count()
    )

    if existing:
        print("Admin already exists. Nothing changed.")
    else:
        name = input("Admin name: ").strip()
        email = input("Admin email: ").strip().lower()
        password = getpass("Admin password: ")
        confirm = getpass("Confirm password: ")

        if len(name) < 3:
            raise ValueError("Name must be at least 3 characters.")
        if len(password) < 8 or len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be 8-72 bytes.")
        if password != confirm:
            raise ValueError("Passwords do not match.")
        if db.query(User).filter(User.email == email).first():
            raise ValueError("Email already exists.")

        role = db.query(Role).filter(Role.name == "admin").first()
        if role is None:
            raise ValueError("Admin role not found.")

        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()

        print("Admin created successfully!")
        print("Email:", email)
        print("Role: admin")

except Exception:
    db.rollback()
    raise
finally:
    db.close()
