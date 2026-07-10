from flask import Blueprint, request, jsonify
from models.MaterialEstudio import MaterialEstudio
import json

ws_material = Blueprint('ws_material', __name__, url_prefix='/material')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_material.before_request
def _requiere_token_material_estudio():
    verify_jwt_in_request()

# ws_material.py - registrar_material
@ws_material.route('', methods=['POST'])
def registrar_material():
    data = request.get_json()
    return jsonify(json.loads(MaterialEstudio.registrar(
        data['titulo'],
        data['tipo'],
        data['url'],
        data['tiempo_estimado'],
        data['id_competencia'],
        data.get('nivel')  # opcional
    )))


# Listar todos
@ws_material.route('', methods=['GET'])
def listar_materiales():
    return jsonify(json.loads(MaterialEstudio.listar_todos()))

# Obtener uno por ID
@ws_material.route('/<int:id_material>', methods=['GET'])
def obtener_material(id_material):
    return jsonify(json.loads(MaterialEstudio.obtener(id_material)))

# Actualizar
@ws_material.route('/<int:id_material>', methods=['PUT'])
def actualizar_material(id_material):
    data = request.get_json()
    return jsonify(json.loads(MaterialEstudio.actualizar(id_material, data)))

# Eliminar
@ws_material.route('/<int:id_material>', methods=['DELETE'])
def eliminar_material(id_material):
    return jsonify(json.loads(MaterialEstudio.eliminar(id_material)))
