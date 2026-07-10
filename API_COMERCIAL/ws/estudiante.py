from flask import Blueprint, request, jsonify
from models.Estudiante import Estudiante
from conexionBD import Conexion
import json

ws_estudiante = Blueprint('ws_estudiante', __name__)

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request
from ws._seguridad import verificar_acceso_estudiante, verificar_acceso_usuario

@ws_estudiante.before_request
def _requiere_token_estudiante():
    verify_jwt_in_request()

# =========================================================
# 1. CREAR ESTUDIANTE
# =========================================================
@ws_estudiante.route('/estudiantes', methods=['POST'])
def crear_estudiante():
    data = request.get_json()
    if not data or 'grado' not in data or 'id_usuario' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})

    obj = Estudiante(
        grado=data['grado'],
        id_usuario=data['id_usuario']
    )
    return jsonify(json.loads(obj.crear()))


# =========================================================
# 2. LISTAR ESTUDIANTES
# =========================================================
@ws_estudiante.route('/estudiantes', methods=['GET'])
def listar_estudiantes():
    # Lista global de alumnos: solo para docentes (evita que un alumno
    # descargue el padrón completo de menores).
    from ws._seguridad import identidad
    _, rol = identidad()
    if rol != 'docente':
        return jsonify({'status': False, 'message': 'No autorizado'}), 403
    return jsonify(json.loads(Estudiante.listar()))


# =========================================================
# 3. OBTENER ESTUDIANTE POR ID
# =========================================================
@ws_estudiante.route('/estudiantes/<int:id_estudiante>', methods=['GET'])
def obtener_estudiante(id_estudiante):
    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err
    return jsonify(json.loads(Estudiante.obtener(id_estudiante)))


# =========================================================
# 4. ACTUALIZAR ESTUDIANTE
# =========================================================
@ws_estudiante.route('/estudiantes/<int:id_estudiante>', methods=['PUT'])
def actualizar_estudiante(id_estudiante):
    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err
    data = request.get_json()
    if not data or 'grado' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})

    obj = Estudiante(
        id_estudiante=id_estudiante,
        grado=data['grado']
    )
    return jsonify(json.loads(obj.actualizar()))


# =========================================================
# 5. ELIMINAR ESTUDIANTE
# =========================================================
@ws_estudiante.route('/estudiantes/<int:id_estudiante>', methods=['DELETE'])
def eliminar_estudiante(id_estudiante):
    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err
    return jsonify(json.loads(Estudiante.eliminar(id_estudiante)))


# =========================================================
# 6. OBTENER ESTUDIANTE POR ID_USUARIO
#    GET /estudiantes/por-usuario/<id_usuario>
# ✅ Ahora devuelve también nombre completo en formato
#    "Apellidos, Nombre" para consistencia con el docente
# =========================================================
@ws_estudiante.route('/estudiantes/por-usuario/<int:id_usuario>', methods=['GET'])
def estudiante_por_usuario(id_usuario):
    err = verificar_acceso_usuario(id_usuario)
    if err:
        return err
    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT
                e.id_estudiante,
                e.grado,
                e.estado_estudiante,
                e.id_usuario,
                -- ✅ Nombre completo para mostrar en la app
                TRIM(u.apellidos) || ', ' || TRIM(u.nombre) AS nombre_completo,
                u.nombre    AS nombre,
                u.apellidos AS apellidos
            FROM estudiante e
            JOIN usuarios u ON u.id_usuario = e.id_usuario
            WHERE e.id_usuario = %s
        """, (id_usuario,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                'status':  False,
                'message': 'No se encontró estudiante para ese usuario'
            }), 404

        return jsonify({
            'status': True,
            'data': {
                'id_estudiante':    row['id_estudiante'],
                'grado':            row['grado'],
                'estado_estudiante': row['estado_estudiante'],
                'id_usuario':       row['id_usuario'],
                'nombre_completo':  row['nombre_completo'],
                'nombre':           row['nombre'],
                'apellidos':        row['apellidos']
            }
        }), 200

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500
    finally:
        cur.close()
        con.close()