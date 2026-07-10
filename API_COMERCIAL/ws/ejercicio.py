# API_COMERCIAL/ws/ejercicio.py
from flask import Blueprint, jsonify, request
from conexionBD import Conexion
import json
import os


def _imagen_url(raw: str | None) -> str | None:
    if not raw:
        return None
    # URL completa (Cloudinary, etc.) → se devuelve tal cual
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    # Ruta legacy (/static/... o solo filename) → sirve via endpoint local
    return "/ejercicios/imagen/" + os.path.basename(raw)

ws_ejercicio = Blueprint("ws_ejercicio", __name__, url_prefix="/ejercicios")

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_ejercicio.before_request
def _requiere_token_ejercicio():
    verify_jwt_in_request()

def _normalizar_imagen_rel(imagen_db: str | None) -> str | None:
    """
    Devuelve SIEMPRE:
      - None si no hay imagen
      - una ruta que empieza por '/static/...'
    No arma URLs absolutas, eso lo hace la app móvil.
    """
    if not imagen_db:
        return None

    path = imagen_db.strip()

    # Si por alguna razón ya guardaste una URL absoluta, la dejamos tal cual.
    if path.startswith("http://") or path.startswith("https://"):
        return path

    # /static/...
    if path.startswith("/static/"):
        return path

    # static/...
    if path.startswith("static/"):
        return "/" + path

    # /ejercicios_ayuda/ej_4.jpg  -> /static/ejercicios_ayuda/ej_4.jpg
    if path.startswith("/"):
        return "/static" + path

    # ej_4.jpg o ejercicios_ayuda/ej_4.jpg -> /static/ejercicios_ayuda/ej_4.jpg
    return "/static/" + path


# ============================
#  GET /ejercicios
# ============================
@ws_ejercicio.route("", methods=["GET"])
def listar_ejercicios():
    con = Conexion()
    cursor = con.cursor()

    try:
        cursor.execute(
            """
            SELECT
                e.id_ejercicio,
                e.descripcion,
                e.imagen_url,
                e.respuesta_correcta,
                e.pista,
                e.palabras_clave,
                c.id_competencia,
                c.descripcion AS competencia,
                c.area,
                c.nivel
            FROM ejercicios e
            JOIN competencias c
              ON e.id_competencia = c.id_competencia
            ORDER BY e.id_ejercicio DESC
            """
        )
        rows = cursor.fetchall()

        data = [
            {
                "idEjercicio":      r["id_ejercicio"],
                "enunciado":        r["descripcion"],
                "imagenUrl":        _imagen_url(r["imagen_url"]),
                "respuestaCorrecta":r["respuesta_correcta"],
                "pista":            r["pista"],
                "palabrasClave":    r["palabras_clave"],
                "idCompetencia":    r["id_competencia"],
                "competencia":      r["competencia"],
                "area":             r["area"],
                "nivelCompetencia": r["nivel"],
            }
            for r in rows
        ]

        return jsonify({"status": True, "data": data}), 200

    except Exception as e:
        print("Error en GET /ejercicios:", e)
        return jsonify({"status": False, "message": str(e)}), 500

    finally:
        cursor.close()
        con.close()


# ============================
#  GET /ejercicios/<id>
# ============================
@ws_ejercicio.route("/<int:id_ejercicio>", methods=["GET"])
def obtener_ejercicio(id_ejercicio: int):
    con = Conexion()
    cursor = con.cursor()

    try:
        cursor.execute(
            """
            SELECT
                e.id_ejercicio,
                e.descripcion,
                e.imagen_url,
                e.respuesta_correcta,
                e.pista,
                e.palabras_clave,
                c.id_competencia,
                c.descripcion AS competencia,
                c.area,
                c.nivel
            FROM ejercicios e
            JOIN competencias c
              ON e.id_competencia = c.id_competencia
            WHERE e.id_ejercicio = %s
            """,
            (id_ejercicio,),
        )
        ej = cursor.fetchone()

        if not ej:
            return jsonify({"status": False, "message": "Ejercicio no encontrado"}), 404

        cursor.execute(
            """
            SELECT id_opcion, letra, descripcion, es_correcta
            FROM opciones_ejercicio
            WHERE id_ejercicio = %s
            ORDER BY letra
            """,
            (id_ejercicio,),
        )
        opciones_rows = cursor.fetchall()

        opciones = [
            {
                "idOpcion": o["id_opcion"],
                "letra": o["letra"],
                "texto": o["descripcion"],
                "esCorrecta": o["es_correcta"],
            }
            for o in opciones_rows
        ]

        imagen_norm = _normalizar_imagen_rel(ej["imagen_url"])

        data = {
            "idEjercicio":       ej["id_ejercicio"],
            "enunciado":         ej["descripcion"],
            "imagenUrl":         imagen_norm,
            "respuestaCorrecta": ej["respuesta_correcta"],
            "pista":             ej["pista"],
            "palabrasClave":     ej["palabras_clave"],
            "idCompetencia":     ej["id_competencia"],
            "competencia":       ej["competencia"],
            "area":              ej["area"],
            "nivelCompetencia":  ej["nivel"],
            "opciones":          opciones,
        }

        return jsonify({"status": True, "data": data}), 200

    except Exception as e:
        print("Error en GET /ejercicios/<id>:", e)
        return jsonify({"status": False, "message": str(e)}), 500

    finally:
        cursor.close()
        con.close()
