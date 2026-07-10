from flask import Blueprint, request, jsonify
from models.Competencia import Competencia
import json

ws_competencia = Blueprint('ws_competencia', __name__)

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_competencia.before_request
def _requiere_token_competencia():
    verify_jwt_in_request()

# Crear competencia
@ws_competencia.route('/competencias', methods=['POST'])
def crear_competencia():
    data = request.get_json()
    if not data or 'descripcion' not in data or 'nivel' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})
    obj = Competencia(descripcion=data['descripcion'], nivel=data['nivel'])
    return jsonify(json.loads(obj.crear()))

# Listar competencias
@ws_competencia.route('/competencias', methods=['GET'])
def listar_competencias():
    return jsonify(json.loads(Competencia.listar()))

# Obtener competencia por id
@ws_competencia.route('/competencias/<int:id_competencia>', methods=['GET'])
def obtener_competencia(id_competencia):
    return jsonify(json.loads(Competencia.obtener(id_competencia)))

# Actualizar competencia
@ws_competencia.route('/competencias/<int:id_competencia>', methods=['PUT'])
def actualizar_competencia(id_competencia):
    data = request.get_json()
    if not data or 'descripcion' not in data or 'nivel' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})
    obj = Competencia(id_competencia=id_competencia, descripcion=data['descripcion'], nivel=data['nivel'])
    return jsonify(json.loads(obj.actualizar()))

# Eliminar competencia
@ws_competencia.route('/competencias/<int:id_competencia>', methods=['DELETE'])
def eliminar_competencia(id_competencia):
    return jsonify(json.loads(Competencia.eliminar(id_competencia)))
