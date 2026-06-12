from flask import Blueprint, request, jsonify
from conexionBD import Conexion
import os, secrets, string, smtplib
from email.message import EmailMessage
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash

ws_auth = Blueprint('ws_auth', __name__)

# ==========================================
# CONFIGURACIÓN DEL CORREO EMISOR
# ⚠️  NUNCA pongas credenciales reales aquí (quedan en Git).
#     Define estas variables en Railway / .env local:
#       SMTP_USER=tu@gmail.com
#       SMTP_PASS=xxxx xxxx xxxx xxxx   ← App Password de Gmail
# ==========================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
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

    # 🔒 La API pública solo registra ESTUDIANTES. Los docentes se registran
    #    desde el portal web, que exige el código de institución
    #    (CODIGO_REGISTRO_DOCENTE). Sin este guard, cualquiera podía crearse
    #    una cuenta de docente enviando rol='docente' por Postman/curl.
    rol_solicitado = (data.get('rol') or 'estudiante').strip().lower()
    if rol_solicitado != 'estudiante':
        return jsonify({
            'status': False,
            'message': 'Solo se permite el registro de estudiantes desde la aplicación. '
                       'Los docentes deben registrarse en el portal web.'
        }), 403

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
            'estudiante'          # rol fijo: el guard de arriba rechaza otros roles
        ))

        new_row = cur.fetchone()
        new_id  = new_row['id_usuario']
        rol     = 'estudiante'

        id_docente = None

        cur.execute("""
            INSERT INTO estudiante
                (id_usuario, grado,
                 cantidad, regularidad_equivalencia_cambio,
                 forma_movimiento_localizacion, gestion_datos_incertidumbre,
                 progreso_general, estado_estudiante)
            VALUES (%s, NULL, NULL, NULL, NULL, NULL, 0, 'activo')
            RETURNING id_estudiante
        """, (new_id,))
        est_row       = cur.fetchone()
        id_estudiante = est_row['id_estudiante'] if est_row else None

        con.commit()

        user = {
            'id_usuario':    new_id,
            'nombre':        data['nombre'],
            'apellidos':     data['apellidos'],
            'correo':        data['correo'],
            'rol':           rol,
            'id_docente':    id_docente,
            'id_estudiante': id_estudiante
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

        # Guard: si las credenciales SMTP no están configuradas, abortar antes
        # de tocar la BD (igual que el fix en el proyecto web).
        if not SMTP_USER or not SMTP_PASS:
            cur.close()
            con.close()
            return jsonify({
                'status': False,
                'message': 'El sistema de correo no está configurado. Contacta al administrador.'
            }), 503

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
# ⚠️  REQUIERE JWT — el usuario solo puede cambiar SU PROPIA contraseña.
#     El id_usuario del body se ignora; se usa el del token para evitar
#     que un atacante cambie la contraseña de otro usuario.
# -------------------------------------------------------------------
@ws_auth.route('/auth/cambiar_password', methods=['PUT'])
@jwt_required()
def cambiar_password():
    # Identidad del token (id_usuario como string)
    current_id = int(get_jwt_identity())

    data  = request.get_json() or {}
    nueva = data.get('nueva_password') or data.get('nueva')

    if not nueva:
        return jsonify({'status': False, 'message': 'Falta nueva_password'}), 400
    if len(str(nueva)) < 6:
        return jsonify({'status': False, 'message': 'La contraseña debe tener al menos 6 caracteres'}), 400

    con = Conexion()
    cur = con.cursor()
    try:
        hash_contra = generate_password_hash(nueva)
        cur.execute(
            "UPDATE usuarios SET contrasena=%s WHERE id_usuario=%s",
            (hash_contra, current_id)
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