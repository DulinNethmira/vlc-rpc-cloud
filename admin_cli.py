import argparse
import sys
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import get_password_hash

def bootstrap_admin(email, password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.is_admin = True
            user.password_hash = get_password_hash(password)
            print(f"Updated existing user {email} to admin and reset password.")
        else:
            user = User(
                email=email,
                password_hash=get_password_hash(password),
                is_admin=True
            )
            db.add(user)
            print(f"Created new admin user {email}.")
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap the first admin user.")
    parser.add_argument("email", help="Admin email address")
    parser.add_argument("password", help="Admin password")
    
    args = parser.parse_args()
    bootstrap_admin(args.email, args.password)
