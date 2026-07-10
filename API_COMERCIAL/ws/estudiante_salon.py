from flask import Blueprint, request, jsonify
from models.EstudianteSalon import EstudianteSalon
import json

ws_estudiante_salon = Blueprint('ws_estudiante_salon', __name__, url_prefix='/estudiante_salon')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_estudiante_salon.before_request
def _requiere_token_estudiante_salon():
    verify_jwt_in_request()

# Asignar estudiante a salón
@ws_estudiante_salon.route('', methods=['POST'])
def asignar_estudiante():
    data = request.get_json()
    return jsonify(json.loads(EstudianteSalon.asignar(data['id_estudiante'], data['id_salon'])))

# Listar estudiantes en salones
@ws_estudiante_salon.route('', methods=['GET'])
def listar_estudiantes_salones():
    return jsonify(json.loads(EstudianteSalon.listar()))

# Eliminar asignación
@ws_estudiante_salon.route('/<int:id_estudiante>/<int:id_salon>', methods=['DELETE'])
def eliminar_asignacion(id_estudiante, id_salon):
    return jsonify(json.loads(EstudianteSalon.eliminar(id_estudiante, id_salon)))
