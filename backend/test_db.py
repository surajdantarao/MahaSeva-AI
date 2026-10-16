
from sqlalchemy.exc import SQLAlchemyError

from backend.database import check_database_connection, engine


def main() -> None:
    try:
        database_name = check_database_connection()

        if database_name != "mahaseva_ai":
            raise RuntimeError(
                f"Connected to unexpected database: {database_name}"
            )

        print("MySQL connection successful.")
        print(f"Connected database: {database_name}")

    except (SQLAlchemyError, RuntimeError) as exc:
        raise SystemExit(
            f"MySQL connection failed: {exc}"
        ) from exc

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
