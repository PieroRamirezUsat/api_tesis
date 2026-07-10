from flask import Blueprint, request, jsonify
from models.Puntaje import Puntaje
from models.scoring import score_to_nivel
import json
from conexionBD import Conexion
import datetime

ws_puntaje = Blueprint('ws_puntaje', __name__, url_prefix='/puntaje')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request

@ws_puntaje.before_request
def _requiere_token_puntaje():
    verify_jwt_in_request()

# ── helper: actualiza NEC con score directo (asignación docente) ─────────────
def _sync_nec_desde_puntaje(cursor, id_estudiante, id_competencia, score_directo):
    """
    Cuando el docente asigna un puntaje directamente (0-100), lo
    convierte a nivel usando la fórmula unificada y actualiza NEC.
    """
    nivel_nuevo = score_to_nivel(float(score_directo))
    cursor.execute("""
        INSERT INTO nivel_estudiante_competencia
            (id_estudiante, id_competencia, nivel_actual,
             promedio_puntaje, ejercicios_considerados, fecha_ultimo_update)
        VALUES (%s, %s, %s, %s, 0, NOW())
        ON CONFLICT (id_estudiante, id_competencia) DO UPDATE SET
            nivel_actual        = EXCLUDED.nivel_actual,
            promedio_puntaje    = EXCLUDED.promedio_puntaje,
            fecha_ultimo_update = EXCLUDED.fecha_ultimo_update
    """, (id_estudiante, id_competencia, nivel_nuevo, float(score_directo)))
    return nivel_nuevo


# ── Listar todos los puntajes ────────────────────────────────────────────────
@ws_puntaje.route('', methods=['GET'])
@ws_puntaje.route('/', methods=['GET'])
def listar_puntajes():
    return jsonify(json.loads(Puntaje.listar()))


# ── Obtener puntajes por estudiante ─────────────────────────────────────────
@ws_puntaje.route('/<int:id_estudiante>', methods=['GET'])
def obtener_puntaje(id_estudiante):
    return jsonify(json.loads(Puntaje.obtener_por_estudiante(id_estudiante)))


# ── Crear puntaje (asignación docente) ───────────────────────────────────────
@ws_puntaje.route('', methods=['POST'])
def crear_puntaje():
    data = request.get_json()
    if not data or 'id_estudiante' not in data \
            or 'id_competencia' not in data or 'puntaje' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})

    id_estudiante  = data['id_estudiante']
    id_competencia = data['id_competencia']
    puntaje        = data['puntaje']

    con    = Conexion()
    cursor = con.cursor()
    try:
        # 1) Insertar en historial de puntajes
        cursor.execute("""
            INSERT INTO puntajes (puntaje, fecha_registro, id_competencia, id_estudiante)
            VALUES (%s, %s, %s, %s) RETURNING id_puntaje
        """, (puntaje, datetime.datetime.now(), id_competencia, id_estudiante))
        nuevo_id = cursor.fetchone()['id_puntaje']

        # 2) Sincronizar nivel_estudiante_competencia con la fórmula unificada
        nivel_nuevo = _sync_nec_desde_puntaje(
            cursor, id_estudiante, id_competencia, puntaje
        )

        con.commit()
        return jsonify({
            'status':    True,
            'message':   'Puntaje creado',
            'id_puntaje': nuevo_id,
            'nivel':     nivel_nuevo
        })
    except Exception as e:
        con.rollback()
        return jsonify({'status': False, 'message': str(e)})
    finally:
        cursor.close()
        con.close()


# ── Actualizar puntaje (corrección docente) ──────────────────────────────────
@ws_puntaje.route('/<int:id_puntaje>', methods=['PUT'])
def actualizar_puntaje(id_puntaje):
    data = request.get_json()
    if not data or 'puntaje' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})

    con    = Conexion()
    cursor = con.cursor()
    try:
        # Obtener id_estudiante e id_competencia del registro existente
        cursor.execute("""
            SELECT id_estudiante, id_competencia
            FROM puntajes WHERE id_puntaje = %s
        """, (id_puntaje,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'status': False, 'message': 'Puntaje no encontrado'})

        id_estudiante  = row['id_estudiante']
        id_competencia = row['id_competencia']
        nuevo_puntaje  = data['puntaje']

        # 1) Actualizar registro
        cursor.execute("""
            UPDATE puntajes
            SET puntaje = %s, fecha_registro = %s
            WHERE id_puntaje = %s
        """, (nuevo_puntaje, datetime.datetime.now(), id_puntaje))

        # 2) Recalcular score promedio de todos los puntajes directos de ese
        #    estudiante/competencia y sincronizar NEC
        cursor.execute("""
            SELECT AVG(puntaje) AS avg_p
            FROM puntajes
            WHERE id_estudiante = %s AND id_competencia = %s
        """, (id_estudiante, id_competencia))
        avg_row   = cursor.fetchone() or {}
        score_avg = float(avg_row.get('avg_p') or nuevo_puntaje)

        nivel_nuevo = _sync_nec_desde_puntaje(
            cursor, id_estudiante, id_competencia, score_avg
        )

        con.commit()
        return jsonify({
            'status':  True,
            'message': 'Puntaje actualizado',
            'nivel':   nivel_nuevo
        })
    except Exception as e:
        con.rollback()
        return jsonify({'status': False, 'message': str(e)})
    finally:
        cursor.close()
        con.close()
