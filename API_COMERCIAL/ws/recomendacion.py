from flask import Blueprint, request, jsonify
from models.Recomendacion import Recomendacion
import json

ws_recomendacion = Blueprint('ws_recomendacion', __name__, url_prefix='/recomendacion')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_recomendacion.before_request
def _requiere_token_recomendacion():
    verify_jwt_in_request()

# Registrar recomendación
@ws_recomendacion.route('', methods=['POST'])
def registrar_recomendacion():
    data = request.get_json()
    return jsonify(json.loads(Recomendacion.registrar(
        data['id_estudiante'],
        data['id_ejercicio'],
        data.get('id_respuesta'),
        data['tipo_recomendacion'],
        data['mensaje']
    )))

# Listar recomendaciones de un estudiante
@ws_recomendacion.route('/<int:id_estudiante>', methods=['GET'])
def listar_recomendaciones(id_estudiante):
    return jsonify(json.loads(Recomendacion.listar(id_estudiante)))

# Eliminar recomendación
@ws_recomendacion.route('/<int:id_recomendacion>', methods=['DELETE'])
def eliminar_recomendacion(id_recomendacion):
    return jsonify(json.loads(Recomendacion.eliminar(id_recomendacion)))
