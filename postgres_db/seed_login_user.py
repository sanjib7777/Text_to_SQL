from pwdlib import PasswordHash
from sqlalchemy import select

from postgres_db.database import SessionLocal
from postgres_db.models import User


USERNAME = "suyog"
PASSWORD = "Test@123"
COMPANY_CODE = "01"


def seed_user() -> None:
    password_hash = PasswordHash.recommended().hash(PASSWORD)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == USERNAME))

        if user is None:
            user = User(
                username=USERNAME,
                password_hash=password_hash,
                company_code=COMPANY_CODE,
                role="user",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = password_hash
            user.company_code = COMPANY_CODE
            user.role = user.role or "user"
            user.is_active = True
            action = "updated"

        db.commit()

    print(f"User '{USERNAME}' {action} with company_code='{COMPANY_CODE}'.")


if __name__ == "__main__":
    seed_user()
