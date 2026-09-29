from sqlalchemy import text

from .database import Base, engine

# IMPORTANT:
# Import models so SQLAlchemy knows about all tables.
from .models import (
    User,
    UserBranch,
    Conversation,
    Message,
    QueryRecord,
)


def create_tables():
    print("Connecting to PostgreSQL...")

    try:
        # Test connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("PostgreSQL connection successful.")

        # Create tables
        Base.metadata.create_all(bind=engine)

        # Keep existing installations compatible with the durable result
        # history fields added after the initial table creation.
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS result_columns TEXT"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS result_rows TEXT"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS validated_sql TEXT"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS page INTEGER"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS page_size INTEGER"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS total_pages INTEGER"
            ))
            connection.execute(text(
                "ALTER TABLE query_records "
                "ADD COLUMN IF NOT EXISTS has_more BOOLEAN"
            ))

        print("All PostgreSQL tables created successfully.")

        print("\nCreated tables:")

        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")

    except Exception as e:
        print("\nFailed to connect/create PostgreSQL tables.")
        print(f"Error: {e}")

        raise


if __name__ == "__main__":
    create_tables()