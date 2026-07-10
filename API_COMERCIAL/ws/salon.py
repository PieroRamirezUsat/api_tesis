from flask import Blueprint, request, jsonify
from models.Salon import Salon
import json

ws_salon = Blueprint('ws_salon', __name__, url_prefix='/salon')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_salon.before_request
def _requiere_token_salon():
    verify_jwt_in_request()

# Crear nuevo salón
@ws_salon.route('', methods=['POST'])
def registrar_salon():
    data = request.get_json()
    return jsonify(json.loads(Salon.registrar(
        data['nombre_salon'],
        data['grado']
    )))

# Listar todos los salones
@ws_salon.route('', methods=['GET'])
def listar_salones():
    return jsonify(json.loads(Salon.listar()))

# Actualizar salón
@ws_salon.route('/<int:id_salon>', methods=['PUT'])
def actualizar_salon(id_salon):
    data = request.get_json()
    return jsonify(json.loads(Salon.actualizar(id_salon, data)))

# Eliminar salón
@ws_salon.route('/<int:id_salon>', methods=['DELETE'])
def eliminar_salon(id_salon):
    return jsonify(json.loads(Salon.eliminar(id_salon)))
