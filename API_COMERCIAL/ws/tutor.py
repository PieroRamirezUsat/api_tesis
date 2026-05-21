# ws_tutor.py
import os
import pickle
import numpy as np
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from conexionBD import Conexion

ws_tutor = Blueprint("ws_tutor", __name__, url_prefix="/tutor")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DESARROLLOS_FOLDER = os.path.join(BASE_DIR, "static", "desarrollos_alumno")
os.makedirs(DESARROLLOS_FOLDER, exist_ok=True)

UMBRAL_APROBADO = 60.0

MODEL_PATH    = os.path.join(BASE_DIR, "modelo_tutor.pkl")
MODELO_TUTOR  = None
ENCODER_NIVEL = None

try:
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)
        if isinstance(data, dict):
            MODELO_TUTOR  = data.get("modelo")
            ENCODER_NIVEL = data.get("encoder")
        else:
            MODELO_TUTOR, ENCODER_NIVEL = data
    print("✅ Modelo de tutor cargado desde:", MODEL_PATH)
    try:
        print("👉 n_features_in_:", MODELO_TUTOR.n_features_in_)
    except Exception:
        pass
except Exception as e:
    print("⚠️ No se pudo cargar modelo_tutor.pkl:", e)


# =========================================
# FUNCIONES AUXILIARES ML
# =========================================
def calcular_features_competencia(cursor, id_estudiante, id_competencia):
    cursor.execute("""
        SELECT COUNT(*)  AS total_intentos,
               AVG(puntaje)   AS promedio_puntaje,
               MIN(puntaje)   AS min_puntaje,
               MAX(puntaje)   AS max_puntaje,
               SUM(CASE WHEN puntaje >= %s THEN 1 ELSE 0 END) AS num_aprobados
        FROM puntajes
        WHERE id_estudiante = %s AND id_competencia = %s
    """, (UMBRAL_APROBADO, id_estudiante, id_competencia))

    row = cursor.fetchone()
    if not row:
        return None

    total     = row.get("total_intentos") or 0
    promedio  = row.get("promedio_puntaje")
    min_p     = row.get("min_puntaje")
    max_p     = row.get("max_puntaje")
    aprobados = row.get("num_aprobados") or 0

    if total == 0 or promedio is None:
        return None

    promedio = max(0.0, min(100.0, float(promedio)))
    min_p    = max(0.0, min(100.0, float(min_p or 0)))
    max_p    = max(0.0, min(100.0, float(max_p or 0)))
    tasa     = float(aprobados) / float(total)

    return np.array([[float(total), promedio, min_p, max_p, tasa]], dtype=float)



def predecir_nivel_competencia(cursor, id_estudiante, id_competencia):
    nivel_texto = None

    if MODELO_TUTOR is not None:
        X = calcular_features_competencia(cursor, id_estudiante, id_competencia)
        if X is not None:
            try:
                y_pred      = MODELO_TUTOR.predict(X)[0]
                nivel_texto = ENCODER_NIVEL.inverse_transform([y_pred])[0] \
                              if ENCODER_NIVEL else str(y_pred)
                print(f">>> ML features: {X}")
                print(f">>> ML prediccion: {y_pred}")
                print(f">>> Ajuste aplicado: {nivel_texto}")
                print(f"🤖 ML predijo nivel '{nivel_texto}' "
                      f"para est={id_estudiante} comp={id_competencia}")
            except Exception as e:
                print("Error predicción ML:", e)

    if nivel_texto is None:
        # ✅ FIX: usar nivel_estudiante_competencia en lugar de columnas estáticas
        cursor.execute("""
            SELECT nivel_actual
            FROM nivel_estudiante_competencia
            WHERE id_estudiante = %s
              AND id_competencia = %s
        """, (id_estudiante, id_competencia))
        row_nec = cursor.fetchone()

        if row_nec and row_nec.get("nivel_actual"):
            nivel_actual = int(row_nec["nivel_actual"])
            if nivel_actual <= 2:
                nivel_texto = "bajo"
            elif nivel_actual <= 4:
                nivel_texto = "medio"
            else:
                nivel_texto = "alto"
            print(f"📋 Fallback NEC id_comp={id_competencia}: "
                  f"nivel_actual={nivel_actual} → '{nivel_texto}'")
        else:
            nivel_texto = "bajo"
            print(f"📋 Fallback nuevo estudiante id_comp={id_competencia}: 'bajo'")

    return nivel_texto


def actualizar_nivel_estudiante_competencia(cursor, id_estudiante,
                                            id_competencia, nivel_texto):
    if nivel_texto is None:
        return None, None

    cursor.execute("""
        SELECT nivel_actual FROM nivel_estudiante_competencia
        WHERE id_estudiante = %s AND id_competencia = %s
    """, (id_estudiante, id_competencia))
    row_actual       = cursor.fetchone()
    nivel_actual_bd  = int((row_actual or {}).get("nivel_actual") or 0)

    nivel_objetivo = 2 if nivel_texto == "bajo" else 4 if nivel_texto == "medio" else 6

    if nivel_objetivo < nivel_actual_bd:
        nivel_int = max(nivel_objetivo, nivel_actual_bd - 1)
    else:
        nivel_int = nivel_objetivo

    cursor.execute("""
        SELECT COUNT(*) AS total, AVG(puntaje) AS promedio
        FROM puntajes
        WHERE id_estudiante = %s AND id_competencia = %s
    """, (id_estudiante, id_competencia))
    row      = cursor.fetchone() or {}
    total    = int(row.get("total") or 0)
    promedio = float(row.get("promedio") or 0.0)

    cursor.execute("""
        INSERT INTO nivel_estudiante_competencia
            (id_estudiante, id_competencia, nivel_actual,
             promedio_puntaje, ejercicios_considerados, fecha_ultimo_update)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (id_estudiante, id_competencia) DO UPDATE SET
            nivel_actual            = EXCLUDED.nivel_actual,
            promedio_puntaje        = EXCLUDED.promedio_puntaje,
            ejercicios_considerados = EXCLUDED.ejercicios_considerados,
            fecha_ultimo_update     = EXCLUDED.fecha_ultimo_update
    """, (id_estudiante, id_competencia, nivel_int, promedio, total))

    cursor.execute("""
        SELECT AVG(nivel_actual) AS prom
        FROM nivel_estudiante_competencia
        WHERE id_estudiante = %s
    """, (id_estudiante,))
    prom         = float((cursor.fetchone() or {}).get("prom") or 0)
    nivel_global = "bajo" if prom < 3 else "medio" if prom < 5 else "alto"

    return nivel_int, nivel_global


def actualizar_progreso_estudiante(con, cursor, id_estudiante):
    cursor.execute("""
        SELECT c.area, AVG(p.puntaje) AS promedio
        FROM puntajes p
        JOIN competencias c ON c.id_competencia = p.id_competencia
        WHERE p.id_estudiante = %s AND c.area IS NOT NULL
        GROUP BY c.area
    """, (id_estudiante,))
    rows = cursor.fetchall()

    cant = reg = forma = datos = None
    for row in rows:
        area = row["area"]
        prom = int(round(row["promedio"])) if row["promedio"] is not None else None
        if area == "cantidad":
            cant  = prom
        elif area == "regularidad_equivalencia_cambio":
            reg   = prom
        elif area == "forma_movimiento_localizacion":
            forma = prom
        elif area == "gestion_datos_incertidumbre":
            datos = prom

    valores          = [v for v in [cant, reg, forma, datos] if v is not None]
    progreso_general = int(round(sum(valores) / len(valores))) if valores else None

    cursor.execute("""
        UPDATE estudiante
        SET cantidad                        = COALESCE(%s, cantidad),
            regularidad_equivalencia_cambio = COALESCE(%s, regularidad_equivalencia_cambio),
            forma_movimiento_localizacion   = COALESCE(%s, forma_movimiento_localizacion),
            gestion_datos_incertidumbre     = COALESCE(%s, gestion_datos_incertidumbre),
            progreso_general                = COALESCE(%s, progreso_general)
        WHERE id_estudiante = %s
    """, (cant, reg, forma, datos, progreso_general, id_estudiante))


# =========================================================
#  GET /tutor/ejercicio_siguiente
# =========================================================
@ws_tutor.route("/ejercicio_siguiente", methods=["GET"])
def ejercicio_siguiente():
    id_estudiante = request.args.get("idEstudiante", type=int)
    id_dominio    = request.args.get("idDominio",    type=int)
    ajuste        = request.args.get("ajuste",       type=str)
    modo          = (request.args.get("modo") or "repaso").lower().strip()
    id_evaluacion = request.args.get("idEvaluacion", type=int)

    if not id_estudiante:
        return jsonify({"error": "idEstudiante es obligatorio", "status": False}), 400

    con    = Conexion()
    cursor = con.cursor()

    try:
        # Verificar si el alumno ya completó el número de preguntas de la evaluación
        if modo == "evaluacion" and id_evaluacion:
            cursor.execute("""
                SELECT ev.num_preguntas,
                       COALESCE(er.total_preguntas, 0) AS ya_respondidas
                FROM evaluaciones ev
                LEFT JOIN evaluacion_resultados er
                      ON er.id_evaluacion = ev.id_evaluacion
                     AND er.id_estudiante  = %s
                WHERE ev.id_evaluacion = %s
            """, (id_estudiante, id_evaluacion))
            row_ev = cursor.fetchone()
            if row_ev:
                limite  = int(row_ev["num_preguntas"] or 10)
                ya_resp = int(row_ev["ya_respondidas"] or 0)
                if ya_resp >= limite:
                    return jsonify({
                        "status":        False,
                        "sinEjercicios": True,
                        "mensaje":       "Ya completaste todas las preguntas de esta evaluación.",
                    }), 200

        where  = []
        params = []

        if id_dominio:
            filtros.append("e.id_competencia = %s")
            params.append(id_dominio)

        if ajuste == "mas_dificil":
            where.append("e.nivel >= 2")
        elif ajuste == "mas_facil":
            where.append("e.nivel = 1")
        else:
            id_comp_nivel  = id_dominio or 1
            nivel_predicho = predecir_nivel_competencia(cursor, id_estudiante, id_comp_nivel)
            print(f"🎯 Nivel predicho para ejercicio: '{nivel_predicho}'")

            if nivel_predicho == "alto":
                where.append("e.nivel >= 2")
            elif nivel_predicho == "medio":
                where.append("e.nivel BETWEEN 1 AND 2")
            else:
                where.append("e.nivel = 1")

        if modo == "evaluacion":
            where.append("""
                NOT EXISTS(
                    SELECT 1 FROM respuestas_estudiantes r
                    WHERE r.id_ejercicio  = e.id_ejercicio
                      AND r.id_estudiante = %s
                      AND r.modo          = 'evaluacion'
                )
            """)
        else:
            where.append("""
                NOT EXISTS(
                    SELECT 1 FROM respuestas_estudiantes r
                    WHERE r.id_ejercicio  = e.id_ejercicio
                      AND r.id_estudiante = %s
                      AND r.modo          = 'repaso'
                )
            """)
        params.append(id_estudiante)

        where.append("""
            EXISTS(
                SELECT 1 FROM opciones_ejercicio oe
                WHERE oe.id_ejercicio = e.id_ejercicio
            )
        """)

        where_clause = "WHERE " + " AND ".join(where) if where else ""

        cursor.execute(f"""
            SELECT e.id_ejercicio,
                   e.descripcion  AS enunciado,
                   e.imagen_url,
                   e.pista,
                   e.nivel        AS nivel_ejercicio,
                   c.id_competencia,
                   c.descripcion  AS competencia
            FROM ejercicios e
            JOIN competencias c ON e.id_competencia = c.id_competencia
            {where_clause}
            ORDER BY RANDOM()
            LIMIT 1
        """, tuple(params))

        ejercicio = cursor.fetchone()

        # ===========================================================
        # 5) Si NO hay ejercicios nuevos → permitir reforzar antiguos
        # ===========================================================
        if not ejercicio:
            print("⚠️ No hay ejercicios del nivel predicho. Intentando sin filtro de nivel...")
            where_sin_nivel  = [w for w in where if "e.nivel" not in w]
            where_clause_sin = ("WHERE " + " AND ".join(where_sin_nivel) if where_sin_nivel else "")

            cursor.execute(f"""
                SELECT e.id_ejercicio,
                       e.descripcion  AS enunciado,
                       e.imagen_url,
                       e.pista,
                       e.nivel        AS nivel_ejercicio,
                       c.id_competencia,
                       c.descripcion  AS competencia
                FROM ejercicios e
                JOIN competencias c ON e.id_competencia = c.id_competencia
                {where_clause_sin}
                ORDER BY RANDOM()
                LIMIT 1
            """, tuple(params))
            ejercicio = cursor.fetchone()

        if not ejercicio:
            return jsonify({
                "status":        False,
                "sinEjercicios": True,
                "mensaje":       "No hay más ejercicios disponibles.",
            }), 200

        id_ejercicio   = ejercicio["id_ejercicio"]
        id_competencia = ejercicio["id_competencia"]
        nivel_ej       = ejercicio["nivel_ejercicio"]

        print(f"✅ Ejercicio seleccionado: id={id_ejercicio} nivel={nivel_ej} comp={id_competencia}")

        imagen_url_bd = ejercicio.get("imagen_url")
        print(f"🖼️ Ejercicio {ejercicio.get('id_ejercicio')} imagen_url en BD: {imagen_url_bd}")

        if imagen_url_bd:
            base = request.host_url.rstrip("/")
            nombre = os.path.basename(imagen_url_bd)
            imagen_url = f"{base}/ejercicios/imagen/{nombre}"
        else:
            imagen_url = None

        print(f"🖼️ URL final enviada a Android: {imagen_url}")

        cursor.execute("""
            SELECT id_opcion, letra, descripcion
            FROM opciones_ejercicio
            WHERE id_ejercicio = %s
            ORDER BY letra
        """, (id_ejercicio,))
        opciones = [
            {"idOpcion": o["id_opcion"], "letra": o["letra"], "texto": o["descripcion"]}
            for o in cursor.fetchall()
        ]

        if not opciones:
            return jsonify({
                "status":        False,
                "sinEjercicios": True,
                "mensaje":       "El ejercicio no tiene opciones.",
            }), 200

        pista = ejercicio["pista"] if modo == "repaso" else None

        return jsonify({
            "status":         True,
            "sinEjercicios":  False,
            "idEjercicio":    id_ejercicio,
            "idCompetencia":  id_competencia,
            "enunciado":      ejercicio["enunciado"],
            "imagenUrl":      imagen_url,
            "opciones":       opciones,
            "pista":          pista,
            "modo":           modo,
            "nivelEjercicio": nivel_ej,
            "mensaje":        None,
        }), 200

    except Exception as e:
        print("ERROR en ejercicio_siguiente:", e)
        return jsonify({"status": False, "error": str(e)}), 500

    finally:
        cursor.close()
        con.close()


# =========================================================
#  POST /tutor/responder
#  ✅ Incluye materialSugerido cuando el estudiante falla
# =========================================================
@ws_tutor.route("/responder", methods=["POST"])
def responder():
    data = request.get_json() or {}

    id_estudiante    = data.get("idEstudiante")
    id_ejercicio     = data.get("idEjercicio")
    id_opcion_sel    = data.get("idOpcionSeleccionada")
    tiempo_respuesta = data.get("tiempoRespuesta")
    uso_pista        = bool(data.get("usoPista", False))
    modo             = (data.get("modo") or "repaso").lower().strip()
    id_evaluacion    = data.get("idEvaluacion")
    es_repaso        = (modo == "repaso")

    if not id_estudiante or not id_ejercicio or not id_opcion_sel:
        return jsonify({"status": False, "error": "Faltan campos obligatorios"}), 400

    con    = Conexion()
    cursor = con.cursor()

    try:
        # 1) Verificar opción
        cursor.execute("""
            SELECT o.es_correcta,
                   e.id_competencia,
                   e.nivel AS nivel_ejercicio
            FROM opciones_ejercicio o
            JOIN ejercicios e ON e.id_ejercicio = o.id_ejercicio
            WHERE o.id_opcion = %s
        """, (id_opcion_sel,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": False, "error": "Opción no válida"}), 404

        es_correcta     = bool(row["es_correcta"])
        id_competencia  = row["id_competencia"]
        nivel_ejercicio = row["nivel_ejercicio"]

        # 2) Registrar respuesta
        cursor.execute("""
            INSERT INTO respuestas_estudiantes
                (respuesta_texto, respuesta_imagen, fecha,
                 tiempo_respuesta, uso_pista,
                 id_estudiante, id_ejercicio, id_opcion,
                 desarrollo_url, modo)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s,
                    %s, %s, %s, %s, %s)
            RETURNING id_respuesta
        """, (None, None,
              float(tiempo_respuesta) if tiempo_respuesta else None,
              uso_pista,
              id_estudiante, id_ejercicio, id_opcion_sel,
              None, modo))
        id_respuesta = cursor.fetchone()["id_respuesta"]

        # 3) Puntaje
        puntaje = 100 if es_correcta else 0
        cursor.execute("""
            INSERT INTO puntajes (puntaje, id_competencia, id_estudiante)
            VALUES (%s, %s, %s)
        """, (puntaje, id_competencia, id_estudiante))

        # 4) Progreso
        estado = "correcto" if es_correcta else "incorrecto"
        if uso_pista and es_repaso:
            estado += "_con_pista"

        cursor.execute("""
            INSERT INTO progreso
                (nivel_actual, estado, tiempo_respuesta,
                 id_estudiante, id_ejercicio, modo)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (f"Nivel {nivel_ejercicio}" if nivel_ejercicio else None,
              estado,
              float(tiempo_respuesta) if tiempo_respuesta else None,
              id_estudiante, id_ejercicio, modo))

        # 5) Progreso general
        actualizar_progreso_estudiante(con, cursor, id_estudiante)

        # 6) Evaluación oficial
        if not es_repaso and id_evaluacion:
            # Detalle por pregunta para que el docente vea la respuesta del alumno
            cursor.execute("""
                INSERT INTO evaluacion_respuestas
                    (id_evaluacion, id_estudiante, id_ejercicio, id_opcion, es_correcta, fecha)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id_evaluacion, id_estudiante, id_ejercicio) DO NOTHING
            """, (id_evaluacion, id_estudiante, id_ejercicio, id_opcion_sel, es_correcta))
            cursor.execute("""
                INSERT INTO evaluacion_resultados
                    (id_evaluacion, id_estudiante, estado,
                     total_correctas, total_preguntas, puntaje_total)
                VALUES (%s, %s, 'en_progreso', %s, 1, %s)
                ON CONFLICT (id_evaluacion, id_estudiante) DO UPDATE SET
                    total_correctas = evaluacion_resultados.total_correctas
                                    + EXCLUDED.total_correctas,
                    total_preguntas = evaluacion_resultados.total_preguntas
                                    + EXCLUDED.total_preguntas,
                    puntaje_total   = ROUND(
                        (evaluacion_resultados.total_correctas
                         + EXCLUDED.total_correctas)::NUMERIC
                        / (evaluacion_resultados.total_preguntas
                           + EXCLUDED.total_preguntas) * 100
                    )
            """, (id_evaluacion, id_estudiante,
                  1 if es_correcta else 0,
                  100 if es_correcta else 0))

        # 7) Predicción ML
        nivel_ml_texto        = predecir_nivel_competencia(cursor, id_estudiante, id_competencia)
        nivel_competencia_int = None
        nivel_global_texto    = None

        if nivel_ml_texto is not None:
            nivel_competencia_int, nivel_global_texto = \
                actualizar_nivel_estudiante_competencia(
                    cursor, id_estudiante, id_competencia, nivel_ml_texto
                )

            if nivel_ml_texto == "alto":
                nuevo_ajuste  = "mas_dificil"
                mostrar_pista = False
                mensaje       = "¡Vas muy bien! Subimos la dificultad."
            elif nivel_ml_texto == "medio":
                nuevo_ajuste  = "igual"
                mostrar_pista = es_repaso and (not es_correcta)
                mensaje       = "Mantendremos el nivel actual."
            else:
                nuevo_ajuste  = "mas_facil"
                mostrar_pista = es_repaso
                mensaje       = "Bajaremos la dificultad para reforzar."
        else:
            RAPIDO = 45
            LENTO  = 90
            t      = tiempo_respuesta or 0

            if es_correcta:
                nuevo_ajuste  = "mas_dificil" if t <= RAPIDO else "igual"
                mostrar_pista = False
                mensaje       = "¡Excelente!" if t <= RAPIDO else "Muy bien."
            else:
                nuevo_ajuste  = "mas_facil" if t > LENTO else "igual"
                mostrar_pista = es_repaso
                mensaje       = "Intentemos otro ejercicio."

        # ✅ 8) Material sugerido — solo en repaso cuando el estudiante falla
        # Busca material del módulo Dominio según el nivel y la competencia
        material_sugerido = None
        if es_repaso and not es_correcta:
            try:
                # Nivel bajo → material nivel 1, medio → nivel 2, alto → nivel 3
                nivel_mat = 1
                if nivel_ml_texto == "medio":
                    nivel_mat = 2
                elif nivel_ml_texto == "alto":
                    nivel_mat = 3

                cursor.execute("""
                    SELECT id_material, titulo, tipo, url
                    FROM material_estudio
                    WHERE id_competencia = %s
                      AND nivel <= %s
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (id_competencia, nivel_mat))
                mat = cursor.fetchone()
                if mat:
                    material_sugerido = {
                        "idMaterial": mat["id_material"],
                        "titulo":     mat["titulo"],
                        "tipo":       mat["tipo"],
                        "url":        mat["url"]
                    }
            except Exception as e_mat:
                print("Error buscando material:", e_mat)

        con.commit()

        return jsonify({
            "correcta":            es_correcta,
            "mostrarPista":        mostrar_pista,
            "mensaje":             mensaje,
            "nuevoAjuste":         nuevo_ajuste,
            "idRespuesta":         id_respuesta,
            "modo":                modo,
            "nivelMLCompetencia":  nivel_ml_texto,
            "nivelCompetenciaInt": nivel_competencia_int,
            "nivelGlobal":         nivel_global_texto,
            "materialSugerido":    material_sugerido,   # ✅ NUEVO
        }), 200

    except Exception as e:
        con.rollback()
        print("ERROR en /tutor/responder:", e)
        return jsonify({"status": False, "error": str(e)}), 500

    finally:
        cursor.close()
        con.close()


# =========================================================
#  POST /tutor/subir_desarrollo
# =========================================================
@ws_tutor.route("/subir_desarrollo", methods=["POST"])
def subir_desarrollo():
    id_respuesta = request.form.get("idRespuesta", type=int)
    archivo      = request.files.get("archivo")

    if not id_respuesta or not archivo:
        return jsonify({"status": False, "message": "idRespuesta y archivo son obligatorios"}), 400

    ext         = os.path.splitext(archivo.filename)[1].lower()
    filename    = secure_filename(f"resp_{id_respuesta}{ext}")
    ruta_fisica = os.path.join(DESARROLLOS_FOLDER, filename)

    try:
        archivo.save(ruta_fisica)
        url_abs = (request.host_url.rstrip("/") + f"/static/desarrollos_alumno/{filename}")

        con    = Conexion()
        cursor = con.cursor()
        cursor.execute(
            "UPDATE respuestas_estudiantes SET desarrollo_url = %s WHERE id_respuesta = %s",
            (url_abs, id_respuesta)
        )
        con.commit()

        return jsonify({
            "status": True,
            "message": "Desarrollo subido correctamente",
            "desarrolloUrl": url_abs
        }), 200

    except Exception as e:
        print("!! ERROR al guardar desarrollo:", e)
        con.rollback()
        return jsonify({
            "status": False,
            "message": f"Error al guardar el archivo: {str(e)}"
        }), 500

    finally:
        cursor.close()
        con.close()

        return jsonify({
            "status":        True,
            "message":       "Desarrollo subido correctamente",
            "desarrolloUrl": url_abs
        }), 200

    except Exception as e:
        return jsonify({"status": False, "message": str(e)}), 500


# =========================================================
#  GET /tutor/nivel_actual
# =========================================================
@ws_tutor.route("/nivel_actual", methods=["GET"])
def nivel_actual():
    id_estudiante  = request.args.get("idEstudiante",  type=int)
    id_competencia = request.args.get("idCompetencia", type=int)

    if not id_estudiante or not id_competencia:
        return jsonify({"status": False, "error": "idEstudiante e idCompetencia son obligatorios"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        nivel_ml = predecir_nivel_competencia(cursor, id_estudiante, id_competencia)
        cursor.execute("""
            SELECT COUNT(*) AS total, AVG(puntaje) AS promedio
            FROM puntajes
            WHERE id_estudiante = %s AND id_competencia = %s
        """, (id_estudiante, id_competencia))
        row = cursor.fetchone() or {}

        return jsonify({
            "status":          True,
            "idEstudiante":    id_estudiante,
            "idCompetencia":   id_competencia,
            "nivelML":         nivel_ml,
            "totalIntentos":   int(row.get("total") or 0),
            "promedioPuntaje": float(row.get("promedio") or 0.0),
        }), 200

    except Exception as e:
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()


# =========================================================
#  GET /tutor/sugerencias/<id_est>/<id_comp>
# =========================================================
@ws_tutor.route("/sugerencias/<int:id_estudiante>/<int:id_competencia>", methods=["GET"])
def sugerencias_ejercicios(id_estudiante: int, id_competencia: int):
    limite = request.args.get("limite", default=5, type=int)
    con    = Conexion()
    cursor = con.cursor()

    try:
        nivel_ml = predecir_nivel_competencia(cursor, id_estudiante, id_competencia)

        filtro = ""
        if nivel_ml == "alto":    filtro = "AND e.nivel >= 2"
        elif nivel_ml == "medio": filtro = "AND e.nivel BETWEEN 1 AND 2"
        else:                     filtro = "AND e.nivel = 1"

        cursor.execute(f"""
            SELECT e.id_ejercicio,
                   e.descripcion  AS enunciado,
                   e.imagen_url,
                   e.nivel        AS nivel_ejercicio,
                   c.id_competencia,
                   c.descripcion  AS competencia
            FROM ejercicios e
            JOIN competencias c ON e.id_competencia = c.id_competencia
            WHERE e.id_competencia = %s
              AND NOT EXISTS (
                SELECT 1 FROM respuestas_estudiantes r
                WHERE r.id_ejercicio = e.id_ejercicio AND r.id_estudiante = %s
              )
              {filtro}
            ORDER BY RANDOM()
            LIMIT %s
        """, (id_competencia, id_estudiante, limite))

        ejercicios = cursor.fetchall()
        if not ejercicios:
            return jsonify({"status": True, "nivelML": nivel_ml, "ejercicios": [],
                            "mensaje": "No hay ejercicios recomendados."}), 200

        ids = [e["id_ejercicio"] for e in ejercicios]
        cursor.execute("""
            SELECT id_opcion, letra, descripcion, id_ejercicio
            FROM opciones_ejercicio
            WHERE id_ejercicio = ANY(%s)
            ORDER BY id_ejercicio, letra
        """, (ids,))

        opc_map = {}
        for o in cursor.fetchall():
            opc_map.setdefault(o["id_ejercicio"], []).append({
                "idOpcion": o["id_opcion"], "letra": o["letra"], "texto": o["descripcion"]
            })

        return jsonify({
            "status":  True,
            "nivelML": nivel_ml,
            "ejercicios": [{
                "idEjercicio":    e["id_ejercicio"],
                "idCompetencia":  e["id_competencia"],
                "enunciado":      e["enunciado"],
                "imagenUrl":      e["imagen_url"],
                "nivelEjercicio": e["nivel_ejercicio"],
                "opciones":       opc_map.get(e["id_ejercicio"], []),
                "pista":          None,
            } for e in ejercicios]
        }), 200

    except Exception as e:
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()


# =========================================================
#  GET /tutor/evaluacion/activa
# =========================================================
@ws_tutor.route("/evaluacion/activa", methods=["GET"])
def evaluacion_activa():
    id_estudiante = request.args.get("idEstudiante", type=int)
    if not id_estudiante:
        return jsonify({"status": False, "error": "idEstudiante obligatorio"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT ev.id_evaluacion, ev.titulo, ev.descripcion,
                   ev.fecha_inicio, ev.fecha_fin
            FROM evaluaciones ev
            JOIN estudiante_salones es ON es.id_salon = ev.id_salon
            WHERE es.id_estudiante = %s
              AND ev.estado = 'activa'
              AND (ev.fecha_fin IS NULL OR ev.fecha_fin > NOW())
            ORDER BY ev.fecha_inicio DESC
            LIMIT 1
        """, (id_estudiante,))
        ev = cursor.fetchone()

        if not ev:
            return jsonify({"status": True, "hayEvaluacion": False}), 200

        cursor.execute("""
            SELECT estado FROM evaluacion_resultados
            WHERE id_evaluacion = %s AND id_estudiante = %s
        """, (ev["id_evaluacion"], id_estudiante))
        resultado   = cursor.fetchone()
        ya_completo = bool(resultado and resultado["estado"] == "completado")

        return jsonify({
            "status":        True,
            "hayEvaluacion": True,
            "yaCompleto":    ya_completo,
            "evaluacion": {
                "idEvaluacion": ev["id_evaluacion"],
                "titulo":       ev["titulo"],
                "descripcion":  ev["descripcion"],
                "fechaInicio":  str(ev["fecha_inicio"]) if ev["fecha_inicio"] else None,
                "fechaFin":     str(ev["fecha_fin"])    if ev["fecha_fin"]    else None,
            }
        }), 200

    except Exception as e:
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()


# =========================================================
#  POST /tutor/evaluacion/finalizar
# =========================================================
@ws_tutor.route("/evaluacion/finalizar", methods=["POST"])
def finalizar_evaluacion():
    data          = request.get_json() or {}
    id_estudiante = data.get("idEstudiante")
    id_evaluacion = data.get("idEvaluacion")

    if not id_estudiante or not id_evaluacion:
        return jsonify({"status": False, "error": "Faltan parámetros"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        cursor.execute("""
            UPDATE evaluacion_resultados
            SET estado    = 'completado',
                fecha_fin = NOW()
            WHERE id_evaluacion = %s AND id_estudiante = %s
            RETURNING puntaje_total, total_correctas, total_preguntas
        """, (id_evaluacion, id_estudiante))
        row = cursor.fetchone()
        con.commit()

        if not row:
            return jsonify({"status": False, "error": "No se encontró resultado"}), 404

        return jsonify({
            "status":         True,
            "puntajeTotal":   row["puntaje_total"],
            "totalCorrectas": row["total_correctas"],
            "totalPreguntas": row["total_preguntas"],
        }), 200

    except Exception as e:
        con.rollback()
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()

# =========================================================
#  POST /tutor/material/abrir
#  ✅ Registra cuando el alumno abre el material sugerido
# =========================================================
@ws_tutor.route("/material/abrir", methods=["POST"])
def registrar_apertura_material():
    data          = request.get_json() or {}
    id_estudiante = data.get("idEstudiante")
    id_material   = data.get("idMaterial")

    if not id_estudiante or not id_material:
        return jsonify({"ok": False, "error": "Faltan parámetros"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        # ✅ INSERT simple — todas las columnas son nullable, solo necesitamos estas
        cursor.execute("""
            INSERT INTO historial_material_estudio
                (id_estudiante, id_material, estado, veces_revisado, fecha_acceso)
            VALUES (%s, %s, 'visto', 1, NOW())
        """, (id_estudiante, id_material))
        con.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        con.rollback()
        print("Error registrando apertura material:", e)
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()