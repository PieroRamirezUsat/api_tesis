from flask import Blueprint, request, jsonify
from models.Progreso import Progreso
from conexionBD import Conexion
import json

ws_progreso = Blueprint('ws_progreso', __name__, url_prefix='/progreso')

# ==========================
#  POST /progreso
# ==========================
@ws_progreso.route('', methods=['POST'])
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
def listar_progreso():
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
def resumen_progreso():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

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

        # Promedio por competencia (todas las 4 MINEDU)
        cur.execute("""
            SELECT
                c.id_competencia,
                AVG(p.puntaje) AS promedio
            FROM competencias c
            LEFT JOIN puntajes p
                   ON p.id_competencia = c.id_competencia
                  AND p.id_estudiante  = %s
            WHERE c.id_competencia BETWEEN 1 AND 4
            GROUP BY c.id_competencia
            ORDER BY c.id_competencia
        """, (id_estudiante,))

        rows_comp = cur.fetchall() or []
        suma = 0
        for row in rows_comp:
            prom = row.get("promedio")
            if prom is not None:
                suma += float(prom)
        porcentaje = max(0, min(100, int(round(suma / 4))))

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
def progreso_por_competencia():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        # porcentaje = ((nivel_actual-1)/6)*70  +  (promedio_puntaje/100)*30
        cursor.execute("""
            SELECT
                c.id_competencia,
                c.descripcion,
                COALESCE(nec.nivel_actual, 0)  AS nivel_actual,
                COALESCE(AVG(p.puntaje), 0)    AS promedio_puntaje
            FROM competencias c
            LEFT JOIN puntajes p
                   ON p.id_competencia = c.id_competencia
                  AND p.id_estudiante  = %s
            LEFT JOIN nivel_estudiante_competencia nec
                   ON nec.id_competencia = c.id_competencia
                  AND nec.id_estudiante  = %s
            WHERE c.id_competencia BETWEEN 1 AND 4
            GROUP BY c.id_competencia, c.descripcion, nec.nivel_actual
            ORDER BY c.id_competencia
        """, (id_estudiante, id_estudiante))

        rows  = cursor.fetchall() or []
        temas = []
        for row in rows:
            nivel_actual     = int(row.get("nivel_actual") or 0)
            promedio_puntaje = float(row.get("promedio_puntaje") or 0)

            pct = max(0, min(100, int(round((nivel_actual / 7) * 100))))

            nombre_nivel = {
                0: "Sin iniciar",
                1: "Iniciando",
                2: "Básico",
                3: "En progreso",
                4: "Intermedio",
                5: "Avanzado",
                6: "Casi experto",
                7: "Dominio completo"
            }.get(nivel_actual, "Sin datos")

            temas.append({
                "idCompetencia":   row["id_competencia"],
                "nombre":          row["descripcion"],
                "porcentaje":      pct,
                "nivelActual":     nivel_actual,
                "nombreNivel":     nombre_nivel,
                "promedioPuntaje": int(round(promedio_puntaje))
            })

        return jsonify({"status": True, "temas": temas}), 200

    except Exception as e:
        print("Error en /progreso/por_competencia:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cur.close()
        con.close()


# ==========================
#  GET /progreso/historial?idEstudiante=4&limite=5&offset=0
#  ✅ Devuelve modo en cada item
#  ✅ Soporta paginación
# ==========================
@ws_progreso.route('/historial', methods=['GET'])
def historial_progreso():
    id_estudiante = request.args.get('idEstudiante', type=int)
    limite        = request.args.get('limite', default=5, type=int)
    offset        = request.args.get('offset', default=0, type=int)

    if not id_estudiante:
        return jsonify({"status": False, "mensaje": "idEstudiante es obligatorio"}), 400

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
                p.fecha,
                p.estado,
                p.id_ejercicio,
                p.estado,
                p.fecha,
                p.modo,
                e.descripcion AS ejercicio,
                e.id_competencia,
                r2.desarrollo_url,
                COUNT(
                    CASE WHEN r.id_opcion IS NOT NULL
                         AND op.es_correcta = FALSE
                         THEN 1 END
                ) AS intentos_incorrectos
            FROM progreso p
            JOIN ejercicios e
                ON e.id_ejercicio = p.id_ejercicio
            LEFT JOIN respuestas_estudiantes r
                ON r.id_estudiante = p.id_estudiante
               AND r.id_ejercicio  = p.id_ejercicio
            LEFT JOIN opciones_ejercicio op
                ON op.id_opcion = r.id_opcion
            LEFT JOIN respuestas_estudiantes r2
                ON r2.id_estudiante = p.id_estudiante
               AND r2.id_ejercicio  = p.id_ejercicio
               AND r2.desarrollo_url IS NOT NULL
               AND r2.id_respuesta = (
                   SELECT r3.id_respuesta
                   FROM respuestas_estudiantes r3
                   WHERE r3.id_estudiante = p.id_estudiante
                     AND r3.id_ejercicio  = p.id_ejercicio
                     AND r3.fecha <= p.fecha
                   ORDER BY r3.id_respuesta DESC
                   LIMIT 1
               )
            WHERE p.id_estudiante = %s
            GROUP BY
                p.id_progreso,
                p.id_ejercicio,
                p.estado,
                p.fecha,
                p.modo,
                e.descripcion,
                e.id_competencia,
                r2.desarrollo_url
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
            intentos  = int(r.get("intentos_incorrectos") or 0)

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
def eliminar_progreso(id_progreso):
    try:
        return jsonify(json.loads(Progreso.eliminar(id_progreso)))
    except Exception as e:
        return jsonify({"status": False, "mensaje": str(e)}), 500