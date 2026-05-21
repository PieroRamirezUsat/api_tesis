from flask import Blueprint, request, jsonify
from conexionBD import Conexion
import secrets, string, smtplib
from email.message import EmailMessage
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash, check_password_hash

ws_auth = Blueprint('ws_auth', __name__)

# ==========================================
# CONFIGURACIÓN DEL CORREO EMISOR
# ==========================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "ww.sco.lol@gmail.com"
SMTP_PASS = "ldea bxfz fqns zpjx"
# ==========================================


# -------------------------------------------------------------------
# LOGIN (para API móvil)
# -------------------------------------------------------------------
@ws_auth.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    correo = data.get('correo')
    password = data.get('contrasena') or data.get('password')

    if not correo or not password:
        return jsonify({'status': False, 'message': 'Faltan campos'}), 400

    con = Conexion()
    cur = con.cursor()

    try:
        # ✅ CORREGIDO: hacemos JOIN con docente y estudiante
        # para obtener id_docente o id_estudiante según el rol
        cur.execute("""
            SELECT 
                u.id_usuario,
                u.nombre,
                u.apellidos,
                u.correo,
                u.rol,
                u.contrasena,
                d.id_docente,
                e.id_estudiante
            FROM usuarios u
            LEFT JOIN docente d ON d.id_usuario = u.id_usuario
            LEFT JOIN estudiante e ON e.id_usuario = u.id_usuario
            WHERE u.correo = %s AND u.estado_usuario = 'activo'
        """, (correo,))
        row = cur.fetchone()

        if (not row) or (not row['contrasena']) or \
           (not check_password_hash(row['contrasena'], password)):
            return jsonify({
                'status': False,
                'message': 'Credenciales inválidas'
            }), 401

        # ✅ Armamos el user con id_docente e id_estudiante incluidos
        user = {
            'id_usuario':   row['id_usuario'],
            'nombre':       row['nombre'],
            'apellidos':    row['apellidos'],
            'correo':       row['correo'],
            'rol':          row['rol'],
            'id_docente':   row['id_docente'],    # None si no es docente
            'id_estudiante': row['id_estudiante'] # None si no es estudiante
        }

        access_token = create_access_token(
            identity=str(user['id_usuario']),
            additional_claims={
                "correo": user['correo'],
                "rol":    user['rol']
            }
        )

        return jsonify({
            'status':  True,
            'message': 'Inicio de sesión satisfactorio. Bienvenido al sistema',
            'data':    user,
            'token':   access_token
        }), 200

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500
    finally:
        cur.close()
        con.close()

# -------------------------------------------------------------------
# REGISTRO
# -------------------------------------------------------------------
@ws_auth.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required = ('nombre', 'apellidos', 'correo', 'contrasena')

    if any(not data.get(k) for k in required):
        return jsonify({'status': False, 'message': 'Faltan campos'}), 400

    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("SELECT 1 FROM usuarios WHERE correo=%s", (data['correo'],))
        if cur.fetchone():
            return jsonify({
                'status': False,
                'message': 'Correo ya registrado'
            }), 409

        hash_contra = generate_password_hash(data['contrasena'])

        cur.execute("""
            INSERT INTO usuarios (nombre, apellidos, correo, contrasena, rol, estado_usuario)
            VALUES (%s,%s,%s,%s,%s,'activo') 
            RETURNING id_usuario
        """, (
            data['nombre'],
            data['apellidos'],
            data['correo'],
            hash_contra,
            data.get('rol', 'estudiante')
        ))

        new_row = cur.fetchone()
        new_id  = new_row['id_usuario']
        con.commit()

        user = {
            'id_usuario':    new_id,
            'nombre':        data['nombre'],
            'apellidos':     data['apellidos'],
            'correo':        data['correo'],
            'rol':           data.get('rol', 'estudiante'),
            'id_docente':    None,
            'id_estudiante': None
        }

        access_token = create_access_token(
            identity=str(user['id_usuario']),
            additional_claims={
                "correo": user['correo'],
                "rol":    user['rol']
            }
        )

        return jsonify({
            'status':  True,
            'message': 'Usuario creado',
            'data':    user,
            'token':   access_token
        }), 201

    except Exception as e:
        try:
            con.rollback()
        except:
            pass
        return jsonify({'status': False, 'message': str(e)}), 500
    finally:
        cur.close()
        con.close()


# -------------------------------------------------------------------
# RECUPERAR CONTRASEÑA
# -------------------------------------------------------------------
@ws_auth.route('/auth/recuperar', methods=['POST'])
def recuperar_contrasena():
    data   = request.get_json() or {}
    correo = data.get('correo', '').strip()

    if not correo:
        return jsonify({
            'status': False,
            'message': 'Debe ingresar un correo electrónico.'
        }), 400

    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT id_usuario, nombre, apellidos, correo
            FROM usuarios 
            WHERE correo=%s AND estado_usuario = 'activo'
        """, (correo,))
        user = cur.fetchone()

        if not user:
            return jsonify({
                'status': False,
                'message': 'Correo no encontrado.'
            }), 404

        alfabeto       = string.ascii_letters + string.digits
        nueva_pass_plana = ''.join(secrets.choice(alfabeto) for _ in range(8))

        asunto = "Recuperación de contraseña - Sistema de Álgebra"
        cuerpo = (
            f"Hola {user['nombre']} {user['apellidos']},\n\n"
            f"Se ha generado una nueva contraseña para tu cuenta:\n\n"
            f"   {nueva_pass_plana}\n\n"
            f"Ahora podrás ingresar con esta nueva contraseña.\n\n"
            f"Te recomendamos cambiarla una vez que ingreses al sistema.\n\n"
            f"Saludos,\n"
            f"Equipo del Sistema de Álgebra"
        )

        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"]    = SMTP_USER
        msg["To"]      = user['correo']
        msg.set_content(cuerpo)

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        hash_contra = generate_password_hash(nueva_pass_plana)
        cur.execute(
            "UPDATE usuarios SET contrasena=%s WHERE id_usuario=%s",
            (hash_contra, user['id_usuario'])
        )
        con.commit()

        return jsonify({
            'status':  True,
            'message': 'Se envió una nueva contraseña al correo registrado.'
        }), 200

    except smtplib.SMTPAuthenticationError:
        return jsonify({
            'status': False,
            'message': 'Error SMTP: verifica las credenciales del correo del sistema.'
        }), 500
    except Exception as e:
        try:
            con.rollback()
        except:
            pass
        return jsonify({'status': False, 'message': str(e)}), 500
    finally:
        cur.close()
        con.close()


# -------------------------------------------------------------------
# CAMBIAR PASSWORD MANUAL
# -------------------------------------------------------------------
@ws_auth.route('/auth/cambiar_password', methods=['PUT'])
def cambiar_password():
    data      = request.get_json() or {}
    id_usuario = data.get('id_usuario')
    nueva     = data.get('nueva_password')

    if not id_usuario or not nueva:
        return jsonify({'status': False, 'message': 'Faltan campos'}), 400

    con = Conexion()
    cur = con.cursor()
    try:
        hash_contra = generate_password_hash(nueva)
        cur.execute(
            "UPDATE usuarios SET contrasena=%s WHERE id_usuario=%s",
            (hash_contra, id_usuario)
        )
        con.commit()
        return jsonify({
            'status':  True,
            'message': 'Contraseña actualizada'
        }), 200
    except Exception as e:
        try:
            con.rollback()
        except:
            pass
        return jsonify({'status': False, 'message': str(e)}), 500
    finally:
        cur.close()
        con.close()