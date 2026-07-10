# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
#  🔒 GUARD DE AUTORIZACIÓN CENTRALIZADO
# ═══════════════════════════════════════════════════════════════════════════
#  Los @jwt_required / before_request de cada módulo garantizan que hay un
#  token VÁLIDO (autenticación). Este módulo añade la AUTORIZACIÓN: que el
#  dueño del token tenga derecho a ver/modificar ESE recurso en concreto.
#
#  Sin esto, cualquier alumno con sesión podía:
#   · leer los datos de OTRO alumno cambiando idEstudiante en la URL (IDOR-R)
#   · editar el perfil (o la contraseña) de OTRO usuario vía /usuarios/{id}
#     /perfil, que tomaba el id de la URL en vez del token (IDOR-W, robo de
#     cuenta).
#
#  Regla:
#   · Alumno  → solo sus propios datos (id_estudiante ligado a su id_usuario).
#   · Docente → solo los alumnos matriculados en SUS salones.
#
#  Cada verificador devuelve None si el acceso es válido, o una tupla
#  (respuesta_json, código) lista para `return` desde el endpoint.
# ═══════════════════════════════════════════════════════════════════════════
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt
from conexionBD import Conexion


def identidad():
    """(id_usuario:int|None, rol:str|None) del token actual."""
    try:
        uid = int(get_jwt_identity())
    except Exception:
        uid = None
    rol = None
    try:
        rol = (get_jwt() or {}).get("rol")
    except Exception:
        pass
    return uid, rol


def _estudiante_de_usuario(cur, id_usuario):
    cur.execute("SELECT id_estudiante FROM estudiante WHERE id_usuario = %s", (id_usuario,))
    r = cur.fetchone()
    return (r["id_estudiante"] if r else None)


def _docente_de_usuario(cur, id_usuario):
    cur.execute("SELECT id_docente FROM docente WHERE id_usuario = %s", (id_usuario,))
    r = cur.fetchone()
    return (r["id_docente"] if r else None)


def _docente_tiene_estudiante(cur, id_usuario_docente, id_estudiante):
    cur.execute("""
        SELECT 1
        FROM docente d
        JOIN docente_salones ds     ON ds.id_docente   = d.id_docente
        JOIN estudiante_salones es   ON es.id_salon     = ds.id_salon
        WHERE d.id_usuario = %s AND es.id_estudiante = %s
        LIMIT 1
    """, (id_usuario_docente, id_estudiante))
    return cur.fetchone() is not None


def _no_autorizado(msg="No autorizado para acceder a este recurso", code=403):
    return jsonify({"status": False, "error": msg}), code


def verificar_acceso_estudiante(id_estudiante):
    """El token es el propio alumno, o un docente dueño de su salón."""
    uid, rol = identidad()
    if uid is None:
        return _no_autorizado("No autorizado", 401)
    con = Conexion()
    cur = con.cursor()
    try:
        if rol == "docente":
            if _docente_tiene_estudiante(cur, uid, id_estudiante):
                return None
            return _no_autorizado("El estudiante no pertenece a tus salones")
        # Alumno (o rol desconocido): solo sus propios datos
        propio = _estudiante_de_usuario(cur, uid)
        if propio is not None and propio == id_estudiante:
            return None
        return _no_autorizado("No puedes acceder a datos de otro estudiante")
    except Exception as e:
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cur.close()
        con.close()


def verificar_es_mismo_usuario(id_usuario):
    """Solo el dueño del token puede modificar SU propia cuenta."""
    uid, _ = identidad()
    if uid is None:
        return _no_autorizado("No autorizado", 401)
    if uid == id_usuario:
        return None
    return _no_autorizado("Solo puedes modificar tu propia cuenta")


def verificar_acceso_usuario(id_usuario):
    """Leer un perfil: el propio usuario, o un docente sobre un alumno suyo."""
    uid, rol = identidad()
    if uid is None:
        return _no_autorizado("No autorizado", 401)
    if uid == id_usuario:
        return None
    if rol == "docente":
        con = Conexion()
        cur = con.cursor()
        try:
            est = _estudiante_de_usuario(cur, id_usuario)
            if est is not None and _docente_tiene_estudiante(cur, uid, est):
                return None
        finally:
            cur.close()
            con.close()
    return _no_autorizado("No autorizado para ver este usuario")


def verificar_es_docente(id_docente):
    """El token corresponde a ESE docente (no a otro)."""
    uid, _ = identidad()
    if uid is None:
        return _no_autorizado("No autorizado", 401)
    con = Conexion()
    cur = con.cursor()
    try:
        propio = _docente_de_usuario(cur, uid)
        if propio is not None and propio == id_docente:
            return None
        return _no_autorizado("No autorizado para ver datos de otro docente")
    finally:
        cur.close()
        con.close()