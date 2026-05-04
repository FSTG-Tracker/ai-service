from __future__ import annotations

import bz2
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import dlib
import numpy as np
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "presence.db"
STUDENTS_DIR = BASE_DIR / "students"
MODELS_DIR = BASE_DIR / "pretrained_model"
SHAPE_PREDICTOR_PATH = MODELS_DIR / "shape_predictor_68_face_landmarks.dat"
FACE_ENCODER_PATH = MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat"


@dataclass
class FaceModels:
    pose_predictor: dlib.shape_predictor
    face_encoder: dlib.face_recognition_model_v1
    face_detector: dlib.fhog_object_detector


def ensure_model_file(model_path: Path) -> Path:
    if model_path.exists():
        return model_path

    compressed_path = model_path.with_suffix(model_path.suffix + ".bz2")
    if not compressed_path.exists():
        raise FileNotFoundError(
            f"Modèle introuvable: {model_path.name} ou {compressed_path.name}"
        )

    with bz2.open(compressed_path, "rb") as compressed_file:
        model_path.write_bytes(compressed_file.read())

    return model_path


def load_models() -> FaceModels:
    shape_predictor_path = ensure_model_file(SHAPE_PREDICTOR_PATH)
    face_encoder_path = ensure_model_file(FACE_ENCODER_PATH)

    return FaceModels(
        pose_predictor=dlib.shape_predictor(str(shape_predictor_path)),
        face_encoder=dlib.face_recognition_model_v1(str(face_encoder_path)),
        face_detector=dlib.get_frontal_face_detector(),
    )


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS etudiants (
            id INTEGER PRIMARY KEY,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            matricule TEXT,
            photo_encoding BLOB NOT NULL
        )
        """
    )

    existing_tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    legacy_presence_table = False
    if "presences" in existing_tables:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(presences)").fetchall()
        }
        if "module_id" not in columns:
            conn.execute("ALTER TABLE presences RENAME TO presences_legacy")
            legacy_presence_table = True

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS presences (
            id INTEGER PRIMARY KEY,
            etudiant_id INTEGER NOT NULL,
            module_id INTEGER NOT NULL,
            date_heure TEXT NOT NULL,
            valide INTEGER DEFAULT 0,
            FOREIGN KEY (etudiant_id) REFERENCES etudiants (id)
        )
        """
    )

    if legacy_presence_table:
        conn.execute(
            """
            INSERT INTO presences (id, etudiant_id, module_id, date_heure, valide)
            SELECT
                id,
                etudiant_id,
                COALESCE(CAST(module AS INTEGER), 0),
                date_heure,
                COALESCE(valide, 0)
            FROM presences_legacy
            """
        )
        conn.execute("DROP TABLE presences_legacy")

    conn.commit()


def parse_student_filename(file_path: Path) -> tuple[str, str, str]:
    parts = file_path.stem.split("_")
    nom = parts[0] if parts else ""
    prenom = parts[1] if len(parts) > 1 else ""
    matricule = parts[2] if len(parts) > 2 else ""
    return nom, prenom, matricule


def encode_face_from_array(
    image_array: np.ndarray, models: FaceModels
) -> np.ndarray | None:
    face_locations = models.face_detector(image_array, 1)
    if len(face_locations) == 0:
        return None

    shape = models.pose_predictor(image_array, face_locations[0])
    return np.array(
        models.face_encoder.compute_face_descriptor(image_array, shape, num_jitters=1)
    )


def upsert_student(
    conn: sqlite3.Connection,
    nom: str,
    prenom: str,
    matricule: str,
    encoding: np.ndarray,
) -> None:
    existing_student = None
    if matricule:
        existing_student = conn.execute(
            "SELECT id FROM etudiants WHERE matricule = ?",
            (matricule,),
        ).fetchone()

    if existing_student is None:
        existing_student = conn.execute(
            """
            SELECT id FROM etudiants
            WHERE nom = ? AND prenom = ? AND COALESCE(matricule, '') = COALESCE(?, '')
            """,
            (nom, prenom, matricule),
        ).fetchone()

    if existing_student:
        conn.execute(
            """
            UPDATE etudiants
            SET nom = ?, prenom = ?, matricule = ?, photo_encoding = ?
            WHERE id = ?
            """,
            (nom, prenom, matricule, encoding.tobytes(), existing_student["id"]),
        )
        return

    conn.execute(
        """
        INSERT INTO etudiants (nom, prenom, matricule, photo_encoding)
        VALUES (?, ?, ?, ?)
        """,
        (nom, prenom, matricule, encoding.tobytes()),
    )


def sync_students_from_directory(
    conn: sqlite3.Connection, models: FaceModels
) -> list[str]:
    messages: list[str] = []
    if not STUDENTS_DIR.exists():
        messages.append(f"Dossier introuvable: {STUDENTS_DIR}")
        return messages

    for file_path in sorted(STUDENTS_DIR.iterdir()):
        if file_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue

        nom, prenom, matricule = parse_student_filename(file_path)
        image_array = np.array(Image.open(file_path).convert("RGB"))
        encoding = encode_face_from_array(image_array, models)

        if encoding is None:
            messages.append(f"Aucun visage détecté dans {file_path.name}")
            continue

        upsert_student(conn, nom, prenom, matricule, encoding)
        messages.append(f"Profil chargé: {file_path.name}")

    conn.commit()
    return messages


def load_students_from_db(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT id, nom, prenom, photo_encoding FROM etudiants ORDER BY id"
    ).fetchall()
    students: list[dict[str, object]] = []
    for row in rows:
        students.append(
            {
                "id": row["id"],
                "name": f"{row['nom']} {row['prenom']}".strip(),
                "encoding": np.frombuffer(row["photo_encoding"], dtype=np.float64),
            }
        )
    return students


def initialize_runtime() -> FaceModels:
    models = load_models()
    with get_connection() as conn:
        ensure_schema(conn)
        sync_students_from_directory(conn, models)
    return models
