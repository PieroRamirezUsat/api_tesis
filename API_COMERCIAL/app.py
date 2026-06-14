from flask import Flask, jsonify, send_file
import mimetypes
from datetime import timedelta
from flask_jwt_extended import JWTManager
from extensions import limiter

# 👇 AGREGAR ESTO JUSTO AQUÍ
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# 👆 HASTA AQUÍ

from config import SecretKey

from ws.estudiante import ws_estudiante
from ws.usuario import ws_usuario
from ws.docente import ws_docente
from ws.ejercicio import ws_ejercicio
from ws.competencia import ws_competencia
from ws.respuesta import ws_respuesta
from ws.puntaje import ws_puntaje
from ws.historial_material import ws_historial_material
from ws.nivel import ws_nivel
from ws.material_estudio import ws_material
from ws.salon import ws_salon
from ws.docente_salon import ws_docente_salon
from ws.estudiante_salon import ws_estudiante_salon
from ws.progreso import ws_progreso
from ws.recomendacion import ws_recomendacion
from ws.tutor import ws_tutor
from ws.dashboard import ws_dashboard
from ws.auth import ws_auth
from ws.dominio import ws_dominio

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = SecretKey.JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)
jwt = JWTManager(app)
limiter.init_app(app)

@app.errorhandler(429)
def ratelimit_handler(_e):
    return jsonify({"status": False, "mensaje": "Demasiados intentos. Espera un momento e intenta de nuevo."}), 429


# ── Migraciones automáticas de columnas (se ejecuta una sola vez al arrancar) ──
def _migrar_columnas_recursos():
    """
    Agrega palabras_clave a ejercicios y id_ejercicio a material_estudio
    si aún no existen. Usa ADD COLUMN IF NOT EXISTS → idempotente.
    """
    try:
        from conexionBD import Conexion
        con = Conexion()
        cur = con.cursor()
        cur.execute(
            "ALTER TABLE ejercicios "
            "ADD COLUMN IF NOT EXISTS palabras_clave VARCHAR(200)"
        )
        cur.execute(
            "ALTER TABLE material_estudio "
            "ADD COLUMN IF NOT EXISTS id_ejercicio INTEGER "
            "REFERENCES ejercicios(id_ejercicio) ON DELETE SET NULL"
        )
        # Normalizar competencias.area de C1 a snake_case como C2-C4:
        # los templates del proyecto web comparan area == 'cantidad'.
        cur.execute(
            "UPDATE competencias SET area = 'cantidad' "
            "WHERE id_competencia = 1 AND area <> 'cantidad'"
        )
        con.commit()
        cur.close()
        con.close()
        print("✅ Migración recursos: columnas listas")
    except Exception as _e:
        print(f"⚠️  Migración recursos (ignorado): {_e}")

_migrar_columnas_recursos()


app.register_blueprint(ws_estudiante)
app.register_blueprint(ws_usuario)
app.register_blueprint(ws_docente)
app.register_blueprint(ws_ejercicio)
app.register_blueprint(ws_competencia)
app.register_blueprint(ws_respuesta)
app.register_blueprint(ws_puntaje)
app.register_blueprint(ws_historial_material)
app.register_blueprint(ws_nivel)
app.register_blueprint(ws_material)
app.register_blueprint(ws_salon)
app.register_blueprint(ws_docente_salon)
app.register_blueprint(ws_estudiante_salon)
app.register_blueprint(ws_progreso)
app.register_blueprint(ws_recomendacion)
app.register_blueprint(ws_tutor)
app.register_blueprint(ws_dashboard)
app.register_blueprint(ws_auth)
app.register_blueprint(ws_dominio)


_EJERCICIOS_AYUDA = os.getenv(
    "EJERCICIOS_AYUDA_PATH",
    os.path.join(BASE_DIR, "static", "ejercicios_ayuda")   # funciona en Windows y Linux
)
_DESARROLLOS_ALUMNO = os.getenv(
    "DESARROLLOS_ALUMNO_PATH",
    os.path.join(BASE_DIR, "static", "desarrollos_alumno")
)
print("📁 Ejercicios ayuda:", _EJERCICIOS_AYUDA, "| existe:", os.path.exists(_EJERCICIOS_AYUDA))
print("📁 Desarrollos alumno:", _DESARROLLOS_ALUMNO, "| existe:", os.path.exists(_DESARROLLOS_ALUMNO))


def _servir_imagen(carpeta, filename):
    """
    Sirve un archivo de imagen desde la carpeta indicada.
    Previene path traversal: solo acepta nombres de archivo sin subdirectorios.
    """
    try:
        # Sanear filename: eliminar cualquier componente de directorio (../../ etc.)
        safe_name = os.path.basename(filename)
        if not safe_name or safe_name != filename:
            # El filename original contenía barras u otros componentes → rechazar
            return jsonify({"error": "Nombre de archivo inválido"}), 400

        filepath = os.path.join(carpeta, safe_name)
        if not os.path.exists(filepath):
            return jsonify({"error": "Imagen no encontrada"}), 404
        mime_type, _ = mimetypes.guess_type(safe_name)
        mime_type = mime_type or 'image/jpeg'
        return send_file(filepath, mimetype=mime_type, max_age=3600)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/ejercicios/imagen/<filename>')
def servir_imagen_ejercicio(filename):
    return _servir_imagen(_EJERCICIOS_AYUDA, filename)


@app.route('/desarrollos/imagen/<filename>')
def servir_imagen_desarrollo(filename):
    """
    Sirve las fotos del desarrollo del alumno.
    Busca en este orden:
      1. _DESARROLLOS_ALUMNO  (Railway Volume o carpeta configurada por env var)
      2. static/desarrollos_alumno/ del repo (fotos comprometidas en git, datos de demo)
    Así funcionan tanto las fotos antiguas (en git) como las nuevas (en el volumen).
    """
    # 1. Carpeta principal (Railway Volume cuando DESARROLLOS_ALUMNO_PATH está seteada)
    ruta_principal = os.path.join(_DESARROLLOS_ALUMNO, filename)
    if os.path.exists(ruta_principal):
        return _servir_imagen(_DESARROLLOS_ALUMNO, filename)

    # 2. Fallback: carpeta estática del repo (datos de demo comprometidos en git)
    static_git = os.path.join(BASE_DIR, "static", "desarrollos_alumno")
    return _servir_imagen(static_git, filename)


@app.route('/')
def home():
    return 'API del Sistema de Aprendizaje en Ejecución'


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "TutorMath API", "version": "1.0"}), 200

if __name__ == '__main__':
    # Solo para tu PC
    app.run(port=3008, debug=True, host='0.0.0.0')

