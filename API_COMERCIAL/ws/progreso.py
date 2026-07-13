from flask import Blueprint, request, jsonify
from models.Progreso import Progreso
from models.scoring import (
    nivel_to_progreso, NIVEL_NOMBRE, BANDA_DIFICULTAD_SQL,
    nivel_to_letra, letra_nombre,
)
from conexionBD import Conexion
from flask_jwt_extended import jwt_required
from ws._seguridad import verificar_acceso_estudiante
import json

ws_progreso = Blueprint('ws_progreso', __name__, url_prefix='/progreso')

# ==========================
#  POST /progreso
# ==========================
@ws_progreso.route('', methods=['POST'])
@jwt_required()
def registrar_progreso():
    try:
        data = request.get_json(force=True)
        id_estudiante    = data.get('id_estudiante')
        id_ejercicio     = data.get('id_ejercicio')
        nivel_actual     = data.get('nivel_actual')
        estado           = data.get('estado')
        tiempo_respuesta = data.get('tiempo_respuesta')

        if id_estudiante is None or id_ejercicio is None \
                or nivel_actual is None or estado is None:
            return jsonify({
                "status": False,
                "mensaje": "Faltan campos obligatorios"
            }), 400

        err = verificar_acceso_estudiante(id_estudiante)
        if err:
            return err

        resp = Progreso.registrar(
            id_estudiante, id_ejercicio,
            nivel_actual, estado, tiempo_respuesta
        )
        return jsonify(json.loads(resp))

    except Exception as e:
        return jsonify({"status": False, "mensaje": str(e)}), 500


# ==========================
#  GET /progreso
# ==========================
@ws_progreso.route('', methods=['GET'])
@jwt_required()
def listar_progreso():
    # Volcado global de progreso: solo docentes (no exponer la actividad de
    # todos los alumnos a cualquier cuenta).
    from ws._seguridad import identidad
    _, rol = identidad()
    if rol != 'docente':
        return jsonify({"status": False, "mensaje": "No autorizado"}), 403
    try:
        return jsonify(json.loads(Progreso.listar_todos()))
    except Exception as e:
        return jsonify({"status": False, "mensaje": str(e)}), 500


# ==========================
#  GET /progreso/resumen?idEstudiante=4
#  ✅ Cuenta ejercicios de TODOS los modos
#  ✅ Lecciones desde historial_material_estudio (nombre correcto)
# ==========================
@ws_progreso.route('/resumen', methods=['GET'])
@jwt_required()
def resumen_progreso():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con = Conexion()
    cur = con.cursor()
    try:
        # Total ejercicios desarrollados (todos los modos)
        cur.execute("""
            SELECT COUNT(*) AS total_ej
            FROM progreso
            WHERE id_estudiante = %s
        """, (id_estudiante,))
        row_total = cur.fetchone() or {}
        total = int(row_total.get("total_ej", 0) or 0)

        # ✅ CORREGIDO: nombre real de la tabla es historial_material_estudio
        cur.execute("""
            SELECT COUNT(DISTINCT id_material) AS total_mat
            FROM historial_material_estudio
            WHERE id_estudiante = %s
        """, (id_estudiante,))
        row_mat = cur.fetchone() or {}
        total_lecciones = int(row_mat.get("total_mat", 0) or 0)

        # Progreso por competencia desde NEC; si NEC vacío usa puntajes diagnóstico
        cur.execute("""
            SELECT
                c.id_competencia,
                COALESCE(
                    nec.nivel_actual,
                    CASE
                        WHEN avg_p.avg_score >= 93 THEN 7
                        WHEN avg_p.avg_score >= 79 THEN 6
                        WHEN avg_p.avg_score >= 65 THEN 5
                        WHEN avg_p.avg_score >= 50 THEN 4
                        WHEN avg_p.avg_score >= 36 THEN 3
                        WHEN avg_p.avg_score >= 22 THEN 2
                        ELSE 1
                    END,
                    1
                ) AS nivel_actual
            FROM competencias c
            LEFT JOIN nivel_estudiante_competencia nec
                   ON nec.id_competencia = c.id_competencia
                  AND nec.id_estudiante  = %s
            LEFT JOIN (
                SELECT id_competencia, AVG(puntaje) AS avg_score
                FROM puntajes
                WHERE id_estudiante = %s
                GROUP BY id_competencia
            ) avg_p ON avg_p.id_competencia = c.id_competencia
            WHERE c.id_competencia BETWEEN 1 AND 4
            ORDER BY c.id_competencia
        """, (id_estudiante, id_estudiante))

        rows_comp  = cur.fetchall() or []
        suma_pct   = sum(nivel_to_progreso(r.get("nivel_actual") or 1) for r in rows_comp)
        porcentaje = int(round(suma_pct / 4)) if rows_comp else 0

        if porcentaje >= 80:
            resumen = "¡Excelente! Dominas todas las competencias."
        elif porcentaje >= 60:
            resumen = "¡Muy bien! Sigue practicando."
        elif porcentaje >= 40:
            resumen = "Vas bien, aún puedes mejorar."
        elif porcentaje > 0:
            resumen = "Falta reforzar algunas competencias."
        else:
            resumen = "¡Empieza a practicar para ver tu progreso!"

        return jsonify({
            "ejerciciosDesarrollados": total,
            "leccionesVistas":         total_lecciones,
            "nivelPorcentaje":         porcentaje,
            "resumenTexto":            resumen,
            "status":                  True
        }), 200

    except Exception as e:
        print("Error en /progreso/resumen:", str(e))
        return jsonify({
            "ejerciciosDesarrollados": 0,
            "leccionesVistas":         0,
            "nivelPorcentaje":         0,
            "resumenTexto":            "Error al calcular el progreso.",
            "status":                  False,
            "mensaje":                 str(e)
        }), 500
    finally:
        cur.close()
        con.close()


# ==========================
#  GET /progreso/por_competencia?idEstudiante=4
#  ✅ Usa todos los puntajes (repaso + evaluación)
# ==========================
@ws_progreso.route('/por_competencia', methods=['GET'])
@jwt_required()
def progreso_por_competencia():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con    = Conexion()
    cursor = con.cursor()
    try:
        # Lee nivel/score desde NEC; si NEC vacío cae en puntajes diagnóstico
        cursor.execute("""
            SELECT
                c.id_competencia,
                c.descripcion,
                COALESCE(
                    nec.nivel_actual,
                    CASE
                        WHEN avg_p.avg_score >= 93 THEN 7
                        WHEN avg_p.avg_score >= 79 THEN 6
                        WHEN avg_p.avg_score >= 65 THEN 5
                        WHEN avg_p.avg_score >= 50 THEN 4
                        WHEN avg_p.avg_score >= 36 THEN 3
                        WHEN avg_p.avg_score >= 22 THEN 2
                        ELSE 1
                    END,
                    1
                ) AS nivel_actual,
                COALESCE(nec.promedio_puntaje, avg_p.avg_score, 0) AS score
            FROM competencias c
            LEFT JOIN nivel_estudiante_competencia nec
                   ON nec.id_competencia = c.id_competencia
                  AND nec.id_estudiante  = %s
            LEFT JOIN (
                SELECT id_competencia, AVG(puntaje) AS avg_score
                FROM puntajes
                WHERE id_estudiante = %s
                GROUP BY id_competencia
            ) avg_p ON avg_p.id_competencia = c.id_competencia
            WHERE c.id_competencia BETWEEN 1 AND 4
            ORDER BY c.id_competencia
        """, (id_estudiante, id_estudiante))

        rows  = cursor.fetchall() or []
        temas = []
        for row in rows:
            nivel_actual = int(row.get("nivel_actual") or 1)
            score        = float(row.get("score") or 0)

            pct          = nivel_to_progreso(nivel_actual)
            nombre_nivel = NIVEL_NOMBRE.get(nivel_actual, "Sin datos")

            _letra = nivel_to_letra(nivel_actual)
            temas.append({
                "idCompetencia":   row["id_competencia"],
                "nombre":          row["descripcion"],
                "porcentaje":      pct,
                "nivelActual":     nivel_actual,
                "nombreNivel":     nombre_nivel,
                "promedioPuntaje": int(round(score)),
                # Calificación literal MINEDU (para las pantallas del docente).
                # Campos ADICIONALES: no rompen a los clientes que no los usan.
                "letraMinedu":     _letra,
                "nombreMinedu":    letra_nombre(_letra),
            })

        return jsonify({"status": True, "temas": temas}), 200

    except Exception as e:
        print("Error en /progreso/por_competencia:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cursor.close()
        con.close()


# ==========================
#  GET /progreso/historial?idEstudiante=4&limite=5&offset=0
#  ✅ Devuelve modo en cada item
#  ✅ Soporta paginación
# ==========================
@ws_progreso.route('/historial', methods=['GET'])
@jwt_required()
def historial_progreso():
    id_estudiante = request.args.get('idEstudiante', type=int)
    limite        = request.args.get('limite', default=5, type=int)
    offset        = request.args.get('offset', default=0, type=int)

    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con = Conexion()
    cur = con.cursor()
    try:
        # Total de registros para saber si hay más
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM progreso
            WHERE id_estudiante = %s
        """, (id_estudiante,))
        total_registros = int((cur.fetchone() or {}).get("total", 0) or 0)

        cur.execute("""
            SELECT
                p.id_progreso,
                p.id_ejercicio,
                p.estado,
                p.fecha,
                p.modo,
                e.descripcion AS ejercicio,
                e.id_competencia,
                r2.desarrollo_url,
                -- Solo cuenta las respuestas incorrectas ANTERIORES a este registro
                -- de progreso para reflejar los intentos de este intento específico.
                (
                    SELECT COUNT(*)
                    FROM respuestas_estudiantes r
                    JOIN opciones_ejercicio op ON op.id_opcion = r.id_opcion
                    WHERE r.id_estudiante = p.id_estudiante
                      AND r.id_ejercicio  = p.id_ejercicio
                      AND op.es_correcta  = FALSE
                      AND r.fecha        <= p.fecha
                ) AS intentos_incorrectos
            FROM progreso p
            JOIN ejercicios e
                ON e.id_ejercicio = p.id_ejercicio
            LEFT JOIN respuestas_estudiantes r2
                ON r2.id_respuesta = (
                    SELECT r3.id_respuesta
                    FROM respuestas_estudiantes r3
                    WHERE r3.id_estudiante  = p.id_estudiante
                      AND r3.id_ejercicio   = p.id_ejercicio
                      AND r3.desarrollo_url IS NOT NULL
                    ORDER BY r3.id_respuesta DESC
                    LIMIT 1
                )
            WHERE p.id_estudiante = %s
            ORDER BY p.id_progreso DESC
            LIMIT %s OFFSET %s
        """, (id_estudiante, limite, offset))

        rows  = cur.fetchall() or []
        items = []

        for r in rows:
            estado_raw = (r.get("estado") or "").strip().lower()
            modo_raw   = (r.get("modo")   or "repaso").strip().lower()

            if estado_raw.startswith("correcto"):
                estado_texto = "Correcto ✅"
            elif estado_raw.startswith("incorrecto"):
                estado_texto = "Incorrecto ❌"
            else:
                estado_texto = r.get("estado") or "Sin datos"

            if modo_raw == "evaluacion":
                modo_texto = "Evaluación"
            else:
                modo_texto = "Revisión"

            fecha_raw = r.get("fecha")
            fecha_str = str(fecha_raw).replace(" ", "T")[:19] if fecha_raw else ""
            intentos  = max(int(r.get("intentos_incorrectos") or 0), 0)

            items.append({
                "idProgreso":          r["id_progreso"],
                "idEjercicio":         r["id_ejercicio"],
                "idCompetencia":       r.get("id_competencia") or 0,
                "desarrolloUrl":       r.get("desarrollo_url") or None,
                "titulo":              f"Ejercicio: {r['ejercicio']}",
                "fecha":               fecha_str,
                "estado":              estado_texto,
                "modo":                modo_texto,
                "intentosIncorrectos": intentos
            })

        hay_mas = (offset + limite) < total_registros

        return jsonify({
            "status":   True,
            "items":    items,
            "total":    total_registros,
            "hayMas":   hay_mas,
            "offset":   offset,
            "limite":   limite
        }), 200

    except Exception as e:
        print("Error en /progreso/historial:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cur.close()
        con.close()


# ==========================
#  DELETE /progreso/<id>
# ==========================
@ws_progreso.route('/<int:id_progreso>', methods=['DELETE'])
@jwt_required()
def eliminar_progreso(id_progreso):
    try:
        return jsonify(json.loads(Progreso.eliminar(id_progreso)))
    except Exception as e:
        return jsonify({"status": False, "mensaje": str(e)}), 500
    


# ==========================
#  GET /progreso/chart?idEstudiante=4
#  Devuelve puntos reales agrupados por hora para el gráfico lineal
# ==========================
@ws_progreso.route('/chart', methods=['GET'])
@jwt_required()
def progreso_chart():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con = Conexion()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('hour', r.fecha), 'DD/MM HH24') || 'h' AS fecha,
                ROUND(
                    100.0 * SUM(CASE WHEN op.es_correcta THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(r.id_respuesta), 0)
                ) AS puntaje
            FROM respuestas_estudiantes r
            JOIN opciones_ejercicio op ON op.id_opcion = r.id_opcion
            WHERE r.id_estudiante = %s
              AND r.fecha IS NOT NULL
            GROUP BY DATE_TRUNC('hour', r.fecha)
            ORDER BY DATE_TRUNC('hour', r.fecha) ASC
            LIMIT 60
        """, (id_estudiante,))

        rows = cur.fetchall() or []
        datos = [
            {
                "fecha":   row["fecha"],
                "puntaje": int(row["puntaje"] or 0)
            }
            for row in rows
        ]

        return jsonify({"status": True, "datos_chart": datos}), 200

    except Exception as e:
        print("Error en /progreso/chart:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cur.close()
        con.close()


# ==========================
#  GET /progreso/tiempo_por_nivel?idEstudiante=4
#
#  Devuelve el tiempo promedio de respuesta y la tasa de acierto
#  agrupados por nivel de dificultad del ejercicio (N1..N4).
#
#  Usado por: ProgresoFragment y TeacherStudentReportActivity
#  para mostrar cuánto tarda el alumno según la dificultad.
#
#  Respuesta:
#  {
#    "status": true,
#    "niveles": [
#      {
#        "nivelEjercicio": 1,
#        "nombreNivel":    "Fácil",
#        "promedioSeg":    148.5,
#        "promedioFormato":"2m 28s",
#        "totalRespuestas": 12,
#        "tasaAcierto":    0.83
#      },
#      ...
#    ]
#  }
# ==========================
@ws_progreso.route('/tiempo_por_nivel', methods=['GET'])
@jwt_required()
def tiempo_por_nivel():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con = Conexion()
    cur = con.cursor()
    try:
        # Agrupa por banda de dificultad 1-4 derivada de la dificultad real
        # (nivel_logro 1-7). La columna legacy `nivel` quedó abandonada en 1.
        cur.execute(f"""
            SELECT
                {BANDA_DIFICULTAD_SQL}                          AS nivel_ejercicio,
                AVG(r.tiempo_respuesta)                         AS promedio_seg,
                COUNT(*)                                        AS total_respuestas,
                AVG(CASE WHEN op.es_correcta THEN 1.0
                         ELSE 0.0 END)                         AS tasa_acierto
            FROM respuestas_estudiantes r
            JOIN ejercicios e
                ON e.id_ejercicio = r.id_ejercicio
            JOIN opciones_ejercicio op
                ON op.id_opcion = r.id_opcion
            WHERE r.id_estudiante    = %s
              AND r.tiempo_respuesta IS NOT NULL
              AND r.tiempo_respuesta > 0
              -- Descarta respuestas con tiempo corrupto (un bug del cliente
              -- llegó a enviar el epoch Unix completo como "segundos de
              -- respuesta" al restaurar un ejercicio ya cargado). 1h es un
              -- techo generoso para responder un solo ejercicio.
              AND r.tiempo_respuesta < 3600
            GROUP BY 1
            ORDER BY 1
        """, (id_estudiante,))

        rows = cur.fetchall() or []

        # Nombres descriptivos para cada nivel de dificultad
        _NOMBRES = {1: "Fácil", 2: "Básico", 3: "Intermedio", 4: "Avanzado"}

        def _fmt(seg):
            """Formatea segundos a '2m 28s'."""
            if seg is None or seg < 0:
                return "—"
            s = int(round(seg))
            m = s // 60
            s = s % 60
            if m >= 60:
                return f"{m//60}h {m%60}m"
            return f"{m}m {s}s" if m else f"{s}s"

        niveles = []
        for r in rows:
            nivel   = int(r["nivel_ejercicio"] or 0)
            prom    = float(r["promedio_seg"] or 0)
            total   = int(r["total_respuestas"] or 0)
            tasa    = float(r["tasa_acierto"] or 0)
            niveles.append({
                "nivelEjercicio":  nivel,
                "nombreNivel":     _NOMBRES.get(nivel, f"N{nivel}"),
                "promedioSeg":     round(prom, 1),
                "promedioFormato": _fmt(prom),
                "totalRespuestas": total,
                "tasaAcierto":     round(tasa, 3),
            })

        return jsonify({"status": True, "niveles": niveles}), 200

    except Exception as e:
        print("Error en /progreso/tiempo_por_nivel:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cur.close()
        con.close()