from contextlib import asynccontextmanager
from datetime import datetime
import io

import numpy as np
import PIL.Image
from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from app_core import (
    encode_face_from_array,
    get_connection,
    initialize_runtime,
    load_students_from_db,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models = initialize_runtime()
    yield


app = FastAPI(lifespan=lifespan)


def get_models(app: FastAPI):
    if not hasattr(app.state, "models"):
        app.state.models = initialize_runtime()
    return app.state.models


@app.post("/verifier-presence")
async def verifier_presence(
    request: Request,
    photo: UploadFile = File(...),
    module_id: int = 1,
):
    # Lire l'image envoyée par le mobile
    contents = await photo.read()
    image = PIL.Image.open(io.BytesIO(contents)).convert("RGB")
    image_array = np.array(image)

    # Encoder le visage capturé
    face_encoding = encode_face_from_array(image_array, get_models(request.app))
    if face_encoding is None:
        return {"match": False, "message": "Aucun visage détecté"}

    # Charger les étudiants enregistrés
    with get_connection() as conn:
        students = load_students_from_db(conn)

    if len(students) == 0:
        return {"match": False, "message": "Base de données vide"}

    # Comparer avec tous les étudiants
    known_encodings = np.array([student["encoding"] for student in students])
    distances = np.linalg.norm(known_encodings - face_encoding, axis=1)
    tolerance = 0.6
    min_distance = float(np.min(distances))
    best_match_index = int(np.argmin(distances))

    if min_distance <= tolerance:
        detected_student = students[best_match_index]
        nom_detecte = str(detected_student["name"])
        score = round(1 - min_distance, 2)

        # Enregistrer la présence
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO presences (etudiant_id, module_id, date_heure, valide)
                VALUES (?, ?, ?, 0)
                """,
                (detected_student["id"], module_id, datetime.now().isoformat()),
            )
            presence_id = cursor.lastrowid
            conn.commit()

        return {
            "match": True,
            "presence_id": presence_id,
            "nom": nom_detecte,
            "score": score,
            "message": "Étudiant reconnu, en attente de validation"
        }
    else:
        return {
            "match": False,
            "score": round(1 - min_distance, 2),
            "message": "Visage non reconnu — utilisez le QR Code"
        }


@app.post("/valider-presence/{presence_id}")
async def valider_presence(presence_id: int):
    """Appelé quand le surveillant appuie sur Valider"""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE presences SET valide = 1 WHERE id = ?",
            (presence_id,),
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Présence introuvable")

    return {"status": "Présence validée"}
