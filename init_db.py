from app_core import get_connection, initialize_runtime, load_students_from_db


def main() -> None:
    initialize_runtime()
    with get_connection() as conn:
        students = load_students_from_db(conn)
    print(f"Base de données prête : {len(students)} étudiant(s) chargé(s)")


if __name__ == "__main__":
    main()
