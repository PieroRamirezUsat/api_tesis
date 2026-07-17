from flask import Blueprint, request, jsonify
from models.Docente import Docente
from models.scoring import nivel_to_progreso
from conexionBD import Conexion
import json

ws_docente = Blueprint('ws_docente', __name__)

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request
from ws._seguridad import verificar_es_docente, identidad

@ws_docente.before_request
def _requiere_token_docente():
    verify_jwt_in_request()

def _solo_docentes():
    """Guard para listados globales: solo cuentas con rol docente."""
    _, rol = identidad()
    if rol != 'docente':
        return jsonify({'status': False, 'message': 'No autorizado'}), 403
    return None

# ========================================
# CRUD BÁSICO DE DOCENTES
# ========================================

@ws_docente.route('/docentes', methods=['POST'])
def crear_docente():
    data = request.get_json() or {}
    if 'especialidad' not in data or 'id_usuario' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})
    obj = Docente(especialidad=data['especialidad'], id_usuario=data['id_usuario'])
    return jsonify(json.loads(obj.crear()))


@ws_docente.route('/docentes', methods=['GET'])
def listar_docentes():
    err = _solo_docentes()
    if err:
        return err
    return jsonify(json.loads(Docente.listar()))


@ws_docente.route('/docentes/<int:id_docente>', methods=['GET'])
def obtener_docente(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    return jsonify(json.loads(Docente.obtener(id_docente)))


@ws_docente.route('/docentes/<int:id_docente>', methods=['PUT'])
def actualizar_docente(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    data = request.get_json() or {}
    if 'especialidad' not in data:
        return jsonify({'status': False, 'message': 'Faltan parámetros'})
    obj = Docente(id_docente=id_docente, especialidad=data['especialidad'])
    return jsonify(json.loads(obj.actualizar()))


@ws_docente.route('/docentes/<int:id_docente>', methods=['DELETE'])
def eliminar_docente(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    return jsonify(json.loads(Docente.eliminar(id_docente)))


# ========================================
# DASHBOARD DEL DOCENTE
# GET /docentes/<id_docente>/dashboard
# ========================================

@ws_docente.route('/docentes/<int:id_docente>/dashboard', methods=['GET'])
def docentes_dashboard(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    return jsonify(json.loads(Docente.dashboard(id_docente)))


# ========================================
# ✅ NUEVO: LISTAR ESTUDIANTES DEL DOCENTE
# GET /docentes/<id_docente>/estudiantes
# Devuelve nombre en formato "Apellidos, Nombre"
# ========================================

@ws_docente.route('/docentes/<int:id_docente>/estudiantes', methods=['GET'])
def docentes_estudiantes(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    """
    Lista todos los estudiantes asignados al salón del docente.
    El nombre se devuelve como: "Apellidos, Nombre"
    para que en la app aparezca ordenado correctamente.

    Respuesta:
    {
      "status": true,
      "data": [
        {
          "id_estudiante": 3,
          "nombre": "Chávez Díaz, Carlos",
          "progreso": 12
        },
        ...
      ]
    }
    """
    con = Conexion()
    cur = con.cursor()

    try:
        # Buscamos los estudiantes vinculados al salón del docente
        # y calculamos su progreso general como promedio de las 4 competencias
        cur.execute("""
            SELECT DISTINCT
                e.id_estudiante,
                -- ✅ Formato: "Apellidos, Nombre"
                TRIM(u.apellidos) || ', ' || TRIM(u.nombre)  AS nombre,
                -- Progreso con la MISMA fórmula que la web y el reporte
                -- (nivel adaptativo NEC): (min(nivel,6)-1)*20 promediado en las
                -- 4 competencias. Antes usaba AVG(puntajes) (= % de acierto),
                -- así que la lista de la app mostraba un número distinto al de
                -- la web para el mismo alumno.
                COALESCE(
                    (
                        SELECT ROUND(AVG((LEAST(nec.nivel_actual, 6) - 1) * 20.0))::int
                        FROM nivel_estudiante_competencia nec
                        WHERE nec.id_estudiante  = e.id_estudiante
                          AND nec.id_competencia BETWEEN 1 AND 4
                    ),
                    0
                ) AS progreso
            FROM estudiante e
            JOIN usuarios u
                ON u.id_usuario = e.id_usuario
            JOIN estudiante_salones es
                ON es.id_estudiante = e.id_estudiante
            JOIN salones s
                ON s.id_salon = es.id_salon
            JOIN docente_salones ds
                ON ds.id_salon = s.id_salon
            WHERE ds.id_docente = %s
              AND e.estado_estudiante = 'activo'
            ORDER BY nombre
        """, (id_docente,))

        rows = cur.fetchall() or []

        data = [
            {
                "id_estudiante": row["id_estudiante"],
                "nombre":        row["nombre"],
                "progreso":      int(row["progreso"] or 0)
            }
            for row in rows
        ]

        return jsonify({
            "status": True,
            "data":   data
        }), 200

    except Exception as e:
        print("Error en /docentes/estudiantes:", str(e))
        return jsonify({
            "status":  False,
            "message": str(e)
        }), 500
    finally:
        cur.close()
        con.close()


# ========================================
# ALERTAS DEL DOCENTE
# GET /docentes/<id_docente>/alertas
# Devuelve alumnos críticos:
#   - promedio < 40 en alguna competencia (nivel bajo)
#   - o >= 3 de sus últimas 5 respuestas fueron incorrectas
# ========================================

@ws_docente.route('/docentes/<int:id_docente>/alertas', methods=['GET'])
def docentes_alertas(id_docente):
    err = verificar_es_docente(id_docente)
    if err:
        return err
    con = Conexion()
    cur = con.cursor()

    try:
        # 1) Todos los estudiantes activos del docente
        cur.execute("""
            SELECT DISTINCT
                e.id_estudiante,
                TRIM(u.apellidos) || ', ' || TRIM(u.nombre) AS nombre
            FROM estudiante e
            JOIN usuarios u         ON u.id_usuario    = e.id_usuario
            JOIN estudiante_salones es ON es.id_estudiante = e.id_estudiante
            JOIN salones s          ON s.id_salon       = es.id_salon
            JOIN docente_salones ds ON ds.id_salon      = s.id_salon
            WHERE ds.id_docente = %s
              AND e.estado_estudiante = 'activo'
              -- Sin diagnóstico inicial el alumno está BLOQUEADO en la app
              -- (no puede practicar): alertar por él es ruido puro. Antes,
              -- un salón recién matriculado generaba 1 falsa alarma de
              -- "bajo rendimiento" por CADA alumno sin notas.
              AND NOT (e.cantidad IS NULL
                       AND e.regularidad_equivalencia_cambio IS NULL
                       AND e.forma_movimiento_localizacion   IS NULL
                       AND e.gestion_datos_incertidumbre     IS NULL)
            ORDER BY nombre
        """, (id_docente,))
        estudiantes = cur.fetchall() or []

        if not estudiantes:
            return jsonify({"status": True, "data": []}), 200

        ids_est = [e["id_estudiante"] for e in estudiantes]
        nombres = {e["id_estudiante"]: e["nombre"] for e in estudiantes}

        # 2) Nivel por competencia por alumno desde NEC (fuente autoritativa)
        cur.execute("""
            SELECT
                e.id_estudiante,
                c.id_competencia,
                c.descripcion,
                COALESCE(nec.nivel_actual, 1) AS nivel_actual
            FROM estudiante e
            CROSS JOIN competencias c
            LEFT JOIN nivel_estudiante_competencia nec
                   ON nec.id_estudiante  = e.id_estudiante
                  AND nec.id_competencia = c.id_competencia
            WHERE e.id_estudiante = ANY(%s)
              AND c.id_competencia BETWEEN 1 AND 4
            ORDER BY e.id_estudiante, c.id_competencia
        """, (ids_est,))
        comp_rows = cur.fetchall() or []

        # 3) Errores recientes — últimas 5 respuestas por alumno
        cur.execute("""
            SELECT
                id_estudiante,
                COUNT(*) AS incorrectas,
                MAX(fecha) AS ultima_actividad
            FROM (
                SELECT
                    id_estudiante,
                    estado,
                    fecha,
                    ROW_NUMBER() OVER (
                        PARTITION BY id_estudiante ORDER BY fecha DESC
                    ) AS rn
                FROM progreso
                WHERE id_estudiante = ANY(%s)
            ) sub
            WHERE rn <= 5
              AND estado ILIKE 'incorrecto%%'
            GROUP BY id_estudiante
        """, (ids_est,))
        errores_map = {
            r["id_estudiante"]: {
                "incorrectas":      int(r["incorrectas"] or 0),
                "ultima_actividad": r["ultima_actividad"].strftime("%d/%m/%Y")
                                    if r["ultima_actividad"] else "Sin actividad"
            }
            for r in (cur.fetchall() or [])
        }

        # 4) Agrupar competencias con problema por alumno
        comp_map = {}
        for r in comp_rows:
            id_est      = r["id_estudiante"]
            nivel_actual = int(r.get("nivel_actual") or 1)
            progreso_pct = nivel_to_progreso(nivel_actual)
            if progreso_pct < 40:  # nivel 1 (0%) o nivel 2 (20%) → problema
                comp_map.setdefault(id_est, []).append({
                    "idCompetencia": r["id_competencia"],
                    "nombre":        r["descripcion"],
                    "promedio":      progreso_pct,
                    "nivel":         "bajo"
                })

        # 5) Construir lista de alertas
        alertas = []
        for id_est in ids_est:
            comps_problema  = comp_map.get(id_est, [])
            err_data        = errores_map.get(id_est, {"incorrectas": 0, "ultima_actividad": "Sin actividad"})
            incorrectas     = err_data["incorrectas"]
            ultima_actividad = err_data["ultima_actividad"]

            # Sin competencias en riesgo y menos de 3 fallos recientes → no alertar
            if not comps_problema and incorrectas < 3:
                continue

            # muchos_errores tiene prioridad si hay ≥3 fallos recientes (más urgente)
            # bajo_rendimiento si el nivel en las competencias es bajo aunque no falle tanto
            tipo = "muchos_errores" if incorrectas >= 3 else "bajo_rendimiento"
            alertas.append({
                "id_estudiante":        id_est,
                "nombre":               nombres[id_est],
                "tipoAlerta":           tipo,
                "competenciasProblema": comps_problema,
                "erroresRecientes":     incorrectas,
                "ultimaActividad":      ultima_actividad,
            })

        return jsonify({"status": True, "data": alertas}), 200

    except Exception as e:
        print("Error en /docentes/alertas:", str(e))
        return jsonify({"status": False, "message": str(e)}), 500
    finally:
        cur.close()
        con.close()