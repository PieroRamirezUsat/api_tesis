from flask import Blueprint, request, jsonify
from models.Respuesta import Respuesta
from models.Puntaje import Puntaje
from conexionBD import Conexion
import json

ws_respuesta = Blueprint('ws_respuesta', __name__)

# ===============================
#  POST /respuestas
#  Crear respuesta + actualizar puntaje
# ===============================
@ws_respuesta.route('/respuestas', methods=['POST'])
def crear_respuesta():
    try:
        data = request.get_json() or {}

        if (
            'respuesta_texto' not in data or
            'id_estudiante' not in data or
            'id_ejercicio' not in data or
            'id_opcion' not in data
        ):
            return jsonify({'status': False, 'message': 'Faltan parámetros'}), 400

        obj = Respuesta(
            respuesta_texto=data['respuesta_texto'],
            id_estudiante=data['id_estudiante'],
            id_ejercicio=data['id_ejercicio'],
            id_opcion=data['id_opcion']
        )

        # Registrar respuesta
        resultado = json.loads(obj.crear())

        # Si la respuesta se registró correctamente, actualizar puntaje
        if resultado.get('status'):
            Puntaje.actualizar_puntaje(
                id_estudiante=data['id_estudiante'],
                id_ejercicio=data['id_ejercicio'],
                id_opcion=data['id_opcion']
            )
            resultado['message'] = resultado.get('message', '') + ' y puntaje actualizado'

        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


# ===============================
#  GET /respuestas
#  Listar todas las respuestas
# ===============================
@ws_respuesta.route('/respuestas', methods=['GET'])
def listar_respuestas():
    try:
        return jsonify(json.loads(Respuesta.listar())), 200
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


# ===============================
#  GET /respuestas/<id>
#  Obtener una respuesta por id
# ===============================
@ws_respuesta.route('/respuestas/<int:id_respuesta>', methods=['GET'])
def obtener_respuesta(id_respuesta):
    try:
        return jsonify(json.loads(Respuesta.obtener(id_respuesta))), 200
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


# ===============================
#  DELETE /respuestas/<id>
#  Eliminar respuesta
# ===============================
@ws_respuesta.route('/respuestas/<int:id_respuesta>', methods=['DELETE'])
def eliminar_respuesta(id_respuesta):
    try:
        return jsonify(json.loads(Respuesta.eliminar(id_respuesta))), 200
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


# ===============================
#  PUT /respuestas/<id>
#  Actualizar respuesta + puntaje
# ===============================
@ws_respuesta.route('/respuestas/<int:id_respuesta>', methods=['PUT'])
def actualizar_respuesta(id_respuesta):
    try:
        data = request.get_json() or {}

        if (
            'respuesta_texto' not in data or
            'id_opcion' not in data or
            'id_estudiante' not in data or
            'id_ejercicio' not in data
        ):
            return jsonify({'status': False, 'message': 'Faltan parámetros'}), 400

        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                UPDATE respuestas_estudiantes
                SET respuesta_texto = %s,
                    id_opcion = %s,
                    fecha = NOW()
                WHERE id_respuesta = %s;
            """
            cursor.execute(sql, (
                data['respuesta_texto'],
                data['id_opcion'],
                id_respuesta
            ))
            con.commit()

            # actualizar puntaje después de la edición
            Puntaje.actualizar_puntaje(
                id_estudiante=data['id_estudiante'],
                id_ejercicio=data['id_ejercicio'],
                id_opcion=data['id_opcion']
            )

            return jsonify({'status': True, 'message': 'Respuesta y puntaje actualizados'}), 200

        except Exception as e:
            con.rollback()
            return jsonify({'status': False, 'message': str(e)}), 500
        finally:
            cursor.close()
            con.close()

    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500
