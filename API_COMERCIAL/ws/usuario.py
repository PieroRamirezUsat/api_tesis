from flask import Blueprint, request, jsonify
from models.Usuario import Usuario
from werkzeug.security import generate_password_hash
import json

ws_usuario = Blueprint('ws_usuario', __name__)

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_usuario.before_request
def _requiere_token_usuario():
    verify_jwt_in_request()

# =========================================================
# ❌ ENDPOINT ELIMINADO: POST /usuario/login (legacy)
#    Duplicaba POST /auth/login (ws/auth.py), que es la versión correcta
#    y la única que usa Android (AuthService). Se elimina para reducir
#    superficie de ataque y no mantener dos logins en paralelo.
# =========================================================


# =========================================================
# 4. ACTUALIZAR USUARIO (PUT /usuarios/<id_usuario>)
# =========================================================
@ws_usuario.route('/usuarios/<int:id_usuario>', methods=['PUT'])
def actualizar_usuario(id_usuario):
    data = request.get_json()
    if not data or 'nombre' not in data or 'apellidos' not in data or 'correo' not in data or 'rol' not in data or 'estado_usuario' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})

    obj = Usuario(
        id_usuario=id_usuario,
        nombre=data['nombre'],
        apellidos=data['apellidos'],
        correo=data['correo'],
        rol=data['rol'],
        estado_usuario=data['estado_usuario']
    )
    return jsonify(json.loads(obj.actualizar()))


# =========================================================
# 4A. OBTENER USUARIO POR ID (GET /usuarios/<id_usuario>)
#      -> LO QUE USA ProfileFragment (RetrofitClient.api.getUsuario)
# =========================================================
@ws_usuario.route('/usuarios/<int:id_usuario>', methods=['GET'])
def obtener_usuario(id_usuario):
    from conexionBD import Conexion
    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT id_usuario, nombre, apellidos, correo, rol, estado_usuario
            FROM usuarios
            WHERE id_usuario = %s
        """, (id_usuario,))

        row = cur.fetchone()

        if not row:
            return jsonify({'status': False, 'message': 'Usuario no encontrado'}), 404

        return jsonify({'status': True, 'data': row}), 200

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500

    finally:
        cur.close()
        con.close()


# =========================================================
# 5. ELIMINAR USUARIO
# =========================================================
@ws_usuario.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
def eliminar_usuario(id_usuario):
    return jsonify(json.loads(Usuario.eliminar(id_usuario)))


# =========================================================
# 6. OBTENER USUARIO DESDE ID_ESTUDIANTE
# =========================================================
@ws_usuario.route('/usuarios/por-estudiante/<int:id_estudiante>', methods=['GET'])
def usuario_por_estudiante(id_estudiante):
    from conexionBD import Conexion
    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT u.id_usuario, u.nombre, u.apellidos, u.correo, u.rol, u.estado_usuario
            FROM usuarios u
            JOIN estudiante e ON e.id_usuario = u.id_usuario
            WHERE e.id_estudiante = %s
        """, (id_estudiante,))

        row = cur.fetchone()

        if row:
            return jsonify({'status': True, 'data': row})

        return jsonify({'status': False, 'message': 'No encontrado'})

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)})

    finally:
        cur.close()
        con.close()


# =========================================================
# 7. ACTUALIZAR PERFIL (PUT /usuarios/<id_usuario>/perfil)
# =========================================================
@ws_usuario.route('/usuarios/<int:id_usuario>/perfil', methods=['PUT'])
def actualizar_perfil(id_usuario):
    from conexionBD import Conexion
    data = request.get_json() or {}

    nombre = (data.get('nombre') or '').strip()
    apellidos = (data.get('apellidos') or '').strip()
    correo = (data.get('correo') or '').strip()
    nueva1 = (data.get('nueva_password') or '').strip()
    nueva2 = (data.get('nueva_contrasena') or '').strip()
    nueva_contrasena = nueva1 if nueva1 else nueva2

    if not nombre or not apellidos or not correo:
        return jsonify({'status': False, 'message': 'Faltan parámetros'}), 200

    con = Conexion()
    cur = con.cursor()

    try:
        # Validar que el correo no esté usado por otro usuario
        cur.execute("""
            SELECT 1 FROM usuarios WHERE correo=%s AND id_usuario<>%s
        """, (correo, id_usuario))

        if cur.fetchone():
            return jsonify({'status': False, 'message': 'Correo ya está en uso'}), 409

        sets = ["nombre=%s", "apellidos=%s", "correo=%s"]
        params = [nombre, apellidos, correo]

        # Si hay nueva contraseña, la guardamos encriptada
        if nueva_contrasena:
            hash_nueva = generate_password_hash(nueva_contrasena)
            sets.append("contrasena=%s")
            params.append(hash_nueva)

        params.append(id_usuario)

        sql = f"UPDATE usuarios SET {', '.join(sets)} WHERE id_usuario=%s"
        cur.execute(sql, tuple(params))
        con.commit()

        cur.execute("""
            SELECT id_usuario, nombre, apellidos, correo, rol, estado_usuario
            FROM usuarios
            WHERE id_usuario=%s
        """, (id_usuario,))

        row = cur.fetchone()

        return jsonify({
            'status': True,
            'message': 'Perfil actualizado',
            'data': row
        }), 200

    except Exception as e:
        con.rollback()
        return jsonify({'status': False, 'message': str(e)}), 500

    finally:
        cur.close()
        con.close()
