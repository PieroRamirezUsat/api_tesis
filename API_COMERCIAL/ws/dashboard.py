from flask import Blueprint, jsonify
from conexionBD import Conexion
from models.Progreso import Progreso
import json

ws_dashboard = Blueprint('ws_dashboard', __name__, url_prefix='/dashboard')


# ========================================
# MINI DASHBOARD ESTUDIANTE
# GET /dashboard/mini/<id_estudiante>
# ========================================
@ws_dashboard.route('/mini/<int:id_estudiante>', methods=['GET'])
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
            SELECT u.nombre
            FROM usuarios u
            JOIN estudiante e ON e.id_usuario = u.id_usuario
            WHERE e.id_estudiante = %s
            LIMIT 1
        """, (id_estudiante,))
        row   = cur.fetchone()
        saludo = (row and row.get('nombre')) or "Alumno"

        lista_json = Progreso.listar(id_estudiante)
        payload    = json.loads(lista_json)
        items      = payload.get('data', []) if payload.get('status', False) else []
        total      = len(items)
        correctas  = sum(
            1 for p in items
            if str(p.get('estado', '')).lower().startswith('correcto')
        )
        progreso_general = int(round((correctas / total) * 100)) if total > 0 else 0

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
                COUNT(DISTINCT e.id_ejercicio) AS total_ejercicios,
                COUNT(DISTINCT r.id_ejercicio) AS resueltos
            FROM competencias c
            LEFT JOIN puntajes p
                   ON p.id_competencia = c.id_competencia
                  AND p.id_estudiante = %s
            WHERE c.id_competencia BETWEEN 1 AND 4
            GROUP BY c.id_competencia, c.descripcion
            ORDER BY c.id_competencia
        """, (id_estudiante,))
        temas_rows = cur.fetchall() or []

        temas = []
        for r in temas_rows:
            prom = r.get("promedio")
            pct  = 0 if prom is None else int(round(prom))
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

        # 3) Progreso promedio real (promedio de las 4 competencias)
        cur.execute("""
            SELECT COALESCE(AVG(sub.prom_est), 0) AS promedio_general
            FROM (
                SELECT
                    e.id_estudiante,
                    AVG(p.puntaje) AS prom_est
                FROM docente_salones ds
                JOIN salones s ON s.id_salon = ds.id_salon
                JOIN estudiante_salones es ON es.id_salon = s.id_salon
                JOIN estudiante e ON e.id_estudiante = es.id_estudiante
                LEFT JOIN puntajes p ON p.id_estudiante = e.id_estudiante
                    AND p.id_competencia BETWEEN 1 AND 4
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
                    MAX(hm.fecha_revision)
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