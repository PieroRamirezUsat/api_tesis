from flask import Blueprint, jsonify
from conexionBD import Conexion
from models.scoring import nivel_to_progreso
from flask_jwt_extended import jwt_required

ws_dashboard = Blueprint('ws_dashboard', __name__, url_prefix='/dashboard')


# ========================================
# MINI DASHBOARD ESTUDIANTE
# GET /dashboard/mini/<id_estudiante>
# ========================================
@ws_dashboard.route('/mini/<int:id_estudiante>', methods=['GET'])
@jwt_required()
def mini_dashboard(id_estudiante: int):
    """
    Mini dashboard para el estudiante.

    Ahora usa la MISMA lógica que:
      - /progreso/resumen  -> completitud global (ejercicios resueltos / totales)
      - /progreso/por_competencia -> completitud por competencia

    Respuesta:
    {
      "saludo": "Juan",
      "progresoGeneral": 12,   # 0..100, completitud global
      "promedio": 65,          # promedio de puntajes (0..100)
      "temas": [
        {"nombre": "Resuelve problemas de cantidad", "porcentaje": 0},
        {"nombre": "Resuelve problemas de regularidad, equivalencia y cambio", "porcentaje": 10},
        ...
      ]
    }
    """
    con = Conexion()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT TRIM(u.nombre) || ' ' || TRIM(COALESCE(u.apellidos, '')) AS nombre_completo
            FROM usuarios u
            JOIN estudiante e ON e.id_usuario = u.id_usuario
            WHERE e.id_estudiante = %s
            LIMIT 1
        """, (id_estudiante,))
        row    = cur.fetchone()
        saludo = (row and row.get('nombre_completo', '').strip()) or "Alumno"

        # Progreso general basado en NEC — misma fórmula que /progreso/resumen
        cur.execute("""
            SELECT COALESCE(nec.nivel_actual, 1) AS nivel_actual
            FROM competencias c
            LEFT JOIN nivel_estudiante_competencia nec
                   ON nec.id_competencia = c.id_competencia
                  AND nec.id_estudiante  = %s
            WHERE c.id_competencia BETWEEN 1 AND 4
            ORDER BY c.id_competencia
        """, (id_estudiante,))
        rows_nec = cur.fetchall() or []
        if rows_nec:
            progreso_general = int(round(
                sum(nivel_to_progreso(r['nivel_actual']) for r in rows_nec) / len(rows_nec)
            ))
        else:
            progreso_general = 0

        cur.execute("""
            SELECT COALESCE(ROUND(AVG(puntaje)), 0)::int AS promedio
            FROM puntajes
            WHERE id_estudiante = %s
        """, (id_estudiante,))
        row     = cur.fetchone() or {}
        promedio = row.get('promedio', 0) or 0

        cur.execute("""
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
        temas_rows = cur.fetchall() or []

        temas = []
        for r in temas_rows:
            pct = nivel_to_progreso(r.get("nivel_actual") or 1)
            temas.append({"nombre": r["descripcion"], "porcentaje": pct})

        return jsonify({
            "status":          True,
            "nombreEstudiante": saludo,
            "saludo":          saludo,
            "progresoGeneral": progreso_general,
            "promedio":        int(promedio),
            "temas":           temas
        })

    except Exception as e:
        return jsonify({
            "status":          False,
            "nombreEstudiante": "Alumno",
            "saludo":          "Alumno",
            "progresoGeneral": 0,
            "promedio":        0,
            "temas":           [],
            "error":           str(e)
        }), 500
    finally:
        cur.close()
        con.close()


# ========================================
# DASHBOARD DOCENTE
# GET /dashboard/docente/<id_docente>
# ========================================
@ws_dashboard.route('/docente/<int:id_docente>', methods=['GET'])
@jwt_required()
def dashboard_docente(id_docente: int):
    con = Conexion()
    cur = con.cursor()

    try:
        # 1) Validar docente
        cur.execute("""
            SELECT u.nombre, u.apellidos
            FROM docente d
            JOIN usuarios u ON u.id_usuario = d.id_usuario
            WHERE d.id_docente = %s
            LIMIT 1
        """, (id_docente,))
        row_doc = cur.fetchone()
        if not row_doc:
            return jsonify({
                "status": False,
                "message": "Docente no encontrado",
                "data": None
            }), 404

        # 2) Matriculados activos
        cur.execute("""
            SELECT COUNT(DISTINCT e.id_estudiante) AS activos
            FROM docente_salones ds
            JOIN salones s ON s.id_salon = ds.id_salon
            JOIN estudiante_salones es ON es.id_salon = s.id_salon
            JOIN estudiante e ON e.id_estudiante = es.id_estudiante
            WHERE ds.id_docente = %s
              AND e.estado_estudiante = 'activo'
        """, (id_docente,))
        row_activos        = cur.fetchone() or {}
        estudiantes_activos = int(row_activos.get("activos", 0) or 0)

        # 3) Progreso promedio del salón — MISMA fórmula que el panel web
        #    (ws/docentes.py): por alumno ROUND(AVG((min(nivel,6)-1)*20)) sobre
        #    las 4 competencias del NEC, y promedio entre alumnos. Antes esta
        #    ruta usaba AVG(puntajes) (= % de acierto histórico), así que la app
        #    del docente y el panel web mostraban números DISTINTOS bajo la
        #    misma etiqueta "Progreso promedio".
        cur.execute("""
            SELECT COALESCE(ROUND(AVG(sub.prom_est)), 0) AS promedio_general
            FROM (
                SELECT
                    e.id_estudiante,
                    COALESCE(
                        (SELECT ROUND(AVG((LEAST(nec.nivel_actual, 6) - 1) * 20.0))::int
                         FROM nivel_estudiante_competencia nec
                         WHERE nec.id_estudiante = e.id_estudiante
                           AND nec.id_competencia BETWEEN 1 AND 4),
                        0
                    ) AS prom_est
                FROM docente_salones ds
                JOIN salones s ON s.id_salon = ds.id_salon
                JOIN estudiante_salones es ON es.id_salon = s.id_salon
                JOIN estudiante e ON e.id_estudiante = es.id_estudiante
                WHERE ds.id_docente = %s
                  AND e.estado_estudiante = 'activo'
                GROUP BY e.id_estudiante
            ) sub
        """, (id_docente,))
        row_prom        = cur.fetchone() or {}
        progreso_promedio = float(row_prom.get("promedio_general", 0) or 0)

        # 4) Competencia con más dificultad
        cur.execute("""
            SELECT c.descripcion,
                   AVG(nec.promedio_puntaje) AS promedio_comp
            FROM docente_salones ds
            JOIN salones s ON s.id_salon = ds.id_salon
            JOIN estudiante_salones es ON es.id_salon = s.id_salon
            JOIN nivel_estudiante_competencia nec
                ON nec.id_estudiante = es.id_estudiante
            JOIN competencias c ON c.id_competencia = nec.id_competencia
            WHERE ds.id_docente = %s
            GROUP BY c.descripcion
            ORDER BY promedio_comp ASC
            LIMIT 1
        """, (id_docente,))
        row_tema          = cur.fetchone()
        tema_mas_dificultad = row_tema.get("descripcion") if row_tema else None

        # 5) Actividad reciente — ✅ fechas formateadas
        cur.execute("""
            SELECT
                -- ✅ Formato Apellidos, Nombre
                TRIM(u.apellidos) || ', ' || TRIM(u.nombre) AS estudiante,
                c.descripcion AS tema,
                p.fecha,
                p.estado
            FROM progreso p
            JOIN estudiante e  ON e.id_estudiante = p.id_estudiante
            JOIN usuarios u    ON u.id_usuario    = e.id_usuario
            JOIN ejercicios ej ON ej.id_ejercicio = p.id_ejercicio
            JOIN competencias c ON c.id_competencia = ej.id_competencia
            WHERE e.id_estudiante IN (
                SELECT es.id_estudiante
                FROM docente_salones ds
                JOIN salones s ON s.id_salon = ds.id_salon
                JOIN estudiante_salones es ON es.id_salon = s.id_salon
                WHERE ds.id_docente = %s
            )
            ORDER BY p.fecha DESC
            LIMIT 3
        """, (id_docente,))
        rows_act = cur.fetchall() or []

        actividad_reciente = []
        for r in rows_act:
            estado = (r.get("estado") or "").lower()
            if estado.startswith("correcto"):
                tipo_texto = "completado"
            elif estado.startswith("incorrecto"):
                tipo_texto = "intentado"
            else:
                tipo_texto = "trabajado en"

            # ✅ Formatear fecha ISO → "21 Abr 2026 · 10:09"
            fecha_raw = r.get("fecha")
            if fecha_raw:
                fecha_iso = fecha_raw.isoformat()
                try:
                    partes     = fecha_iso[:19].split("T")
                    fecha_p    = partes[0].split("-")
                    meses      = ["","Ene","Feb","Mar","Abr","May","Jun",
                                  "Jul","Ago","Sep","Oct","Nov","Dic"]
                    hora       = partes[1][:5] if len(partes) > 1 else ""
                    fecha_str  = (f"{fecha_p[2]} {meses[int(fecha_p[1])]} "
                                  f"{fecha_p[0]} · {hora}")
                except Exception:
                    fecha_str = fecha_iso
            else:
                fecha_str = ""

            actividad_reciente.append({
                "tipo":             tipo_texto,
                "nombreEstudiante": r.get("estudiante", ""),
                "tema":             r.get("tema", ""),
                "fecha":            fecha_str
            })

        return jsonify({
            "status":  True,
            "message": "ok",
            "data": {
                "estudiantesActivos":  estudiantes_activos,
                "progresoPromedio":    progreso_promedio,
                "temaMasDificultad":   tema_mas_dificultad,
                "actividadReciente":   actividad_reciente
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status":  False,
            "message": str(e),
            "data":    None
        }), 500
    finally:
        cur.close()
        con.close()


# ========================================
# ✅ NUEVO: FRECUENCIA DE USO POR ESTUDIANTE
# GET /dashboard/docente/<id_docente>/frecuencia
# Ranking de quién usa más la app
# ========================================
@ws_dashboard.route('/docente/<int:id_docente>/frecuencia', methods=['GET'])
@jwt_required()
def frecuencia_uso(id_docente: int):
    """
    Devuelve el ranking de estudiantes ordenado por
    frecuencia de uso (total de interacciones).

    Interacciones = respuestas a ejercicios + materiales vistos

    Respuesta:
    {
      "status": true,
      "data": [
        {
          "id_estudiante": 3,
          "nombre": "Chávez Díaz, Carlos",
          "totalInteracciones": 45,
          "ejerciciosRespondidos": 30,
          "materialesVistos": 15,
          "ultimaActividad": "21 Abr 2026 · 10:09"
        },
        ...
      ]
    }
    """
    con = Conexion()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT
                e.id_estudiante,
                -- ✅ Formato Apellidos, Nombre
                TRIM(u.apellidos) || ', ' || TRIM(u.nombre) AS nombre,

                -- Total ejercicios respondidos
                COUNT(DISTINCT r.id_respuesta) AS ejercicios_respondidos,

                -- Total materiales vistos
                COUNT(DISTINCT hm.id_historial) AS materiales_vistos,

                -- Total interacciones (suma de ambas)
                COUNT(DISTINCT r.id_respuesta) +
                COUNT(DISTINCT hm.id_historial) AS total_interacciones,

                -- Última actividad (la más reciente entre respuestas y materiales)
                GREATEST(
                    MAX(r.fecha),
                    MAX(hm.fecha_acceso)
                ) AS ultima_actividad

            FROM docente_salones ds
            JOIN salones s ON s.id_salon = ds.id_salon
            JOIN estudiante_salones es ON es.id_salon = s.id_salon
            JOIN estudiante e ON e.id_estudiante = es.id_estudiante
            JOIN usuarios u   ON u.id_usuario    = e.id_usuario

            LEFT JOIN respuestas_estudiantes r
                   ON r.id_estudiante = e.id_estudiante

            LEFT JOIN historial_material_estudio hm
                   ON hm.id_estudiante = e.id_estudiante

            WHERE ds.id_docente = %s
              AND e.estado_estudiante = 'activo'

            GROUP BY e.id_estudiante, u.apellidos, u.nombre
            ORDER BY total_interacciones DESC
        """, (id_docente,))

        rows = cur.fetchall() or []
        data = []

        for r in rows:
            # Formatear última actividad
            ultima_raw = r.get("ultima_actividad")
            if ultima_raw:
                try:
                    fecha_iso = ultima_raw.isoformat()
                    partes    = fecha_iso[:19].split("T")
                    fecha_p   = partes[0].split("-")
                    meses     = ["","Ene","Feb","Mar","Abr","May","Jun",
                                 "Jul","Ago","Sep","Oct","Nov","Dic"]
                    hora      = partes[1][:5] if len(partes) > 1 else ""
                    ultima_str = (f"{fecha_p[2]} {meses[int(fecha_p[1])]} "
                                  f"{fecha_p[0]} · {hora}")
                except Exception:
                    ultima_str = str(ultima_raw)
            else:
                ultima_str = "Sin actividad"

            data.append({
                "id_estudiante":        r["id_estudiante"],
                "nombre":               r["nombre"],
                "totalInteracciones":   int(r["total_interacciones"] or 0),
                "ejerciciosRespondidos": int(r["ejercicios_respondidos"] or 0),
                "materialesVistos":     int(r["materiales_vistos"] or 0),
                "ultimaActividad":      ultima_str
            })

        return jsonify({"status": True, "data": data}), 200

    except Exception as e:
        print("Error en /dashboard/docente/frecuencia:", str(e))
        return jsonify({"status": False, "message": str(e)}), 500
    finally:
        cur.close()
        con.close()


# ========================================
# ESTADÍSTICAS DE MATERIALES POR ESTUDIANTE
# GET /dashboard/docente/<id_docente>/materiales-stats?id_estudiante=<id>
# Usado por: panel web (reporte individual) + app móvil docente
# ========================================
@ws_dashboard.route('/docente/<int:id_docente>/materiales-stats', methods=['GET'])
@jwt_required()
def materiales_stats(id_docente: int):
    """
    Devuelve estadísticas de revisión de materiales de estudio para
    un estudiante específico del docente.

    Query param: id_estudiante (obligatorio)

    Respuesta:
    {
      "status": true,
      "resumen": {
        "totalRevisiones": 12,
        "tiempoTotalSeg": 720,
        "materialesDistintos": 5
      },
      "detalle": [
        {
          "titulo": "Interés simple - Khan Academy",
          "tipo": "link",
          "vecesRevisado": 3,
          "tiempoVisto": 180,
          "tiempoMin": 3
        },
        ...
      ]
    }
    """
    from flask import request as flask_request
    id_estudiante = flask_request.args.get('id_estudiante', type=int)

    if not id_estudiante:
        return jsonify({"status": False, "message": "id_estudiante es obligatorio"}), 400

    con = Conexion()
    cur = con.cursor()
    try:
        # Verificar que el estudiante pertenece a un salón del docente
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM estudiante_salones es
            JOIN docente_salones ds ON ds.id_salon = es.id_salon
            WHERE ds.id_docente = %s
              AND es.id_estudiante = %s
        """, (id_docente, id_estudiante))
        row = cur.fetchone()
        if not row or (row.get('cnt') or 0) == 0:
            return jsonify({"status": False, "message": "Estudiante no pertenece a tus salones"}), 403

        # Estadísticas detalladas por material
        cur.execute("""
            SELECT
                m.titulo,
                m.tipo,
                hm.veces_revisado,
                COALESCE(hm.tiempo_visto, 0) AS tiempo_visto
            FROM historial_material_estudio hm
            JOIN material_estudio m ON m.id_material = hm.id_material
            WHERE hm.id_estudiante = %s
            ORDER BY hm.veces_revisado DESC, tiempo_visto DESC
        """, (id_estudiante,))

        rows = cur.fetchall() or []

        detalle = [
            {
                "titulo":       r["titulo"],
                "tipo":         r["tipo"],
                "vecesRevisado": int(r["veces_revisado"] or 0),
                "tiempoVisto":   int(r["tiempo_visto"]   or 0),
                "tiempoMin":     round(int(r["tiempo_visto"] or 0) / 60, 1),
            }
            for r in rows
        ]

        total_revisiones = sum(d["vecesRevisado"] for d in detalle)
        tiempo_total_seg = sum(d["tiempoVisto"]   for d in detalle)

        return jsonify({
            "status": True,
            "resumen": {
                "totalRevisiones":    total_revisiones,
                "tiempoTotalSeg":     tiempo_total_seg,
                "tiempoTotalMin":     round(tiempo_total_seg / 60, 1),
                "materialesDistintos": len(detalle),
            },
            "detalle": detalle,
        }), 200

    except Exception as e:
        print("Error en /dashboard/docente/materiales-stats:", str(e))
        return jsonify({"status": False, "message": str(e)}), 500
    finally:
        cur.close()
        con.close()


# ========================================
# ESTADÍSTICAS GLOBALES DE MATERIALES (salón)
# GET /dashboard/docente/<id_docente>/materiales-salon?id_salon=<id>
# Usado por: docente_dashboard.html (mini-card resumen del salón)
# ========================================
@ws_dashboard.route('/docente/<int:id_docente>/materiales-salon', methods=['GET'])
@jwt_required()
def materiales_salon(id_docente: int):
    """
    Resumen global de revisión de materiales para todos los estudiantes
    de un salón. Usado en el mini-card del dashboard del docente.

    Query param: id_salon (obligatorio)
    """
    from flask import request as flask_request
    id_salon = flask_request.args.get('id_salon', type=int)

    if not id_salon:
        return jsonify({"status": False, "message": "id_salon es obligatorio"}), 400

    con = Conexion()
    cur = con.cursor()
    try:
        # Verificar que el salón pertenece al docente (vía docente_salones)
        cur.execute(
            "SELECT id_salon FROM docente_salones WHERE id_salon = %s AND id_docente = %s",
            (id_salon, id_docente)
        )
        if not cur.fetchone():
            return jsonify({"status": False, "message": "Salón no encontrado"}), 403

        cur.execute("""
            SELECT
                COUNT(DISTINCT hm.id_historial)  AS total_revisiones,
                COUNT(DISTINCT hm.id_estudiante) AS estudiantes_activos,
                SUM(COALESCE(hm.tiempo_visto, 0)) AS tiempo_total_seg,
                u.nombre || ' ' || COALESCE(u.apellidos, '') AS nombre_mas_activo,
                sub.rev_max
            FROM estudiante_salones es
            JOIN estudiante e   ON e.id_estudiante = es.id_estudiante
            JOIN usuarios u     ON u.id_usuario    = e.id_usuario
            LEFT JOIN historial_material_estudio hm ON hm.id_estudiante = e.id_estudiante
            LEFT JOIN (
                SELECT hm2.id_estudiante, SUM(hm2.veces_revisado) AS rev_max
                FROM historial_material_estudio hm2
                JOIN estudiante_salones es2 ON es2.id_estudiante = hm2.id_estudiante
                WHERE es2.id_salon = %s
                GROUP BY hm2.id_estudiante
                ORDER BY rev_max DESC
                LIMIT 1
            ) sub ON sub.id_estudiante = e.id_estudiante
            WHERE es.id_salon = %s
        """, (id_salon, id_salon))

        row = cur.fetchone() or {}

        return jsonify({
            "status":            True,
            "totalRevisiones":   int(row.get("total_revisiones")  or 0),
            "estudiantesActivos": int(row.get("estudiantes_activos") or 0),
            "tiempoTotalMin":    round(int(row.get("tiempo_total_seg") or 0) / 60, 1),
            "alumnoMasActivo":   (row.get("nombre_mas_activo") or "—").strip(),
        }), 200

    except Exception as e:
        print("Error en /dashboard/docente/materiales-salon:", str(e))
        return jsonify({"status": False, "message": str(e)}), 500
    finally:
        cur.close()
        con.close()