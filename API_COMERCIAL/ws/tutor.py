# ws_tutor.py
# ═══════════════════════════════════════════════════════════════════════════
#  📚 GUÍA DE ESTUDIO — EL CORAZÓN DEL TUTOR ADAPTATIVO
# ═══════════════════════════════════════════════════════════════════════════
#  Este módulo implementa el ciclo adaptativo completo que usa la app móvil.
#  Es el archivo MÁS IMPORTANTE de la tesis. El ciclo es:
#
#    1. GET /tutor/ejercicio_siguiente
#       · Lee el nivel del alumno en la competencia (tabla
#         nivel_estudiante_competencia, "NEC" — la fuente autoritativa).
#       · El modelo de ML (modelo_tutor.pkl, árbol de decisión cargado abajo)
#         + la racha de aciertos deciden el "ajuste" (más fácil / igual /
#         más difícil).
#       · Elige al AZAR un ejercicio del banco cuya dificultad (nivel_logro
#         1-7) esté en la banda [nivel-1, nivel+1] (ver NIVEL_EJERCICIO_WHERE
#         en models/scoring.py). Por eso dos alumnos del mismo nivel pueden
#         ver ejercicios distintos.
#
#    2. POST /tutor/responder
#       · Valida la opción contra opciones_ejercicio.es_correcta (el cliente
#         NUNCA decide si es correcta — siempre el servidor).
#       · Guarda la respuesta en respuestas_estudiantes (tiempo, uso_pista).
#       · Calcula el delta de score con models/scoring.calcular_delta()
#         (+8/+5/+2 por acierto según velocidad, −3/−5 por fallo, la pista
#         penaliza) y actualiza el NEC → el nivel puede subir o bajar.
#       · Si falló: 1er fallo → devuelve la pista (mostrarPista);
#         2do fallo → además materialSugerido (material_estudio vinculado a
#         ESTE ejercicio por id_ejercicio) + recursosAdicionales (URLs de
#         búsqueda YouTube/Web/PDF armadas con las palabras_clave).
#
#    3. POST /tutor/subir_desarrollo — foto del desarrollo en papel → va a
#       Cloudinary (producción) o a disco (local). La URL queda en
#       respuestas_estudiantes.desarrollo_url y el docente la ve en la web.
#
#  Otros endpoints: /evaluacion/* (modo examen creado por el docente, sin
#  pistas), /nivel_actual (para la UI), /sugerencias (ejercicios recomendados
#  por el ML), /material/abrir (registra en historial_material_estudio).
#
#  🔧 PARA CAMBIAR ALGO:
#  · Reglas de puntos/tiempos/niveles → models/scoring.py (tablas al inicio).
#  · Re-entrenar el modelo de ML → train_model.py (genera modelo_tutor.pkl).
#  · Qué tan lejos del nivel se eligen ejercicios → NIVEL_EJERCICIO_WHERE.
# ═══════════════════════════════════════════════════════════════════════════
import os
import json
import pickle
import urllib.parse
import numpy as np
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from flask_jwt_extended import jwt_required
from conexionBD import Conexion
from models.scoring import (
    calcular_delta, score_to_nivel, nivel_to_progreso,
    nivel_display_texto, NIVEL_EJERCICIO_WHERE, NIVEL_NOMBRE,
    DIFICULTAD_SQL,
)

ws_tutor = Blueprint("ws_tutor", __name__, url_prefix="/tutor")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# En Railway: apuntar a un volumen persistente mediante la variable DESARROLLOS_ALUMNO_PATH
# Ej: DESARROLLOS_ALUMNO_PATH=/mnt/desarrollos
# En local: usa la carpeta static/desarrollos_alumno/ (ya tiene fotos de prueba)
DESARROLLOS_FOLDER = os.getenv(
    "DESARROLLOS_ALUMNO_PATH",
    os.path.join(BASE_DIR, "static", "desarrollos_alumno")
)
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
# FUNCIONES AUXILIARES
# =========================================

def calcular_features_competencia(cursor, id_estudiante, id_competencia):
    """
    7 features para el árbol de decisión:
      total_intentos   — cuántas veces ha intentado
      promedio_puntaje — promedio histórico (0-100)
      min_puntaje      — peor resultado (detecta lagunas)
      max_puntaje      — mejor resultado (techo alcanzado)
      std_puntaje      — consistencia (std=0 → muy consistente)
      tasa_aprobados   — fracción de intentos correctos
      tendencia        — CORR(orden_temporal, puntaje): +1 mejorando / -1 empeorando
    """
    # ── Estadísticas globales ────────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*)                                              AS total_intentos,
               AVG(puntaje)                                         AS promedio_puntaje,
               MIN(puntaje)                                         AS min_puntaje,
               MAX(puntaje)                                         AS max_puntaje,
               COALESCE(STDDEV(puntaje), 0)                        AS std_puntaje,
               SUM(CASE WHEN puntaje >= %s THEN 1 ELSE 0 END)      AS num_aprobados,
               CORR(EXTRACT(EPOCH FROM fecha_registro), puntaje)   AS tendencia
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
    std_p     = row.get("std_puntaje") or 0.0
    aprobados = row.get("num_aprobados") or 0
    tendencia = row.get("tendencia")         # puede ser NULL si todos puntajes iguales

    if total == 0 or promedio is None:
        return None

    promedio  = max(0.0, min(100.0, float(promedio)))
    min_p     = max(0.0, min(100.0, float(min_p or 0)))
    max_p     = max(0.0, min(100.0, float(max_p or 0)))
    std_p     = max(0.0, float(std_p))
    tasa      = float(aprobados) / float(total)
    tendencia = float(tendencia) if tendencia is not None else 0.0
    # CORR puede estar fuera de [-1,1] por redondeo numérico → clampear
    tendencia = max(-1.0, min(1.0, tendencia))

    return np.array([[float(total), promedio, min_p, max_p, std_p, tasa, tendencia]],
                    dtype=float)


def leer_nec(cursor, id_estudiante, id_competencia):
    """
    Lee nivel_actual y score (promedio_puntaje) de NEC.
    Si no existe el registro inicializa con nivel=1, score=0.
    Retorna (nivel_actual: int, score: float).
    """
    cursor.execute("""
        SELECT nivel_actual, COALESCE(promedio_puntaje, 0) AS score
        FROM nivel_estudiante_competencia
        WHERE id_estudiante = %s AND id_competencia = %s
    """, (id_estudiante, id_competencia))
    row = cursor.fetchone()
    if row:
        return int(row.get("nivel_actual") or 1), float(row.get("score") or 0)
    # Sin registro: puede ser alumno nuevo. Si hay puntaje asignado por docente,
    # inicializar desde ahí.
    cursor.execute("""
        SELECT AVG(puntaje) AS avg_p
        FROM puntajes
        WHERE id_estudiante = %s AND id_competencia = %s
    """, (id_estudiante, id_competencia))
    row_p = cursor.fetchone() or {}
    score_ini = float(row_p.get("avg_p") or 0)
    nivel_ini = score_to_nivel(score_ini)
    cursor.execute("""
        INSERT INTO nivel_estudiante_competencia
            (id_estudiante, id_competencia, nivel_actual,
             promedio_puntaje, ejercicios_considerados, fecha_ultimo_update)
        VALUES (%s, %s, %s, %s, 0, NOW())
        ON CONFLICT (id_estudiante, id_competencia) DO NOTHING
    """, (id_estudiante, id_competencia, nivel_ini, score_ini))
    return nivel_ini, score_ini


def guardar_nec(cursor, id_estudiante, id_competencia, nuevo_score, nuevo_nivel):
    cursor.execute("""
        INSERT INTO nivel_estudiante_competencia
            (id_estudiante, id_competencia, nivel_actual,
             promedio_puntaje, ejercicios_considerados, fecha_ultimo_update)
        VALUES (%s, %s, %s, %s, 0, NOW())
        ON CONFLICT (id_estudiante, id_competencia) DO UPDATE SET
            nivel_actual        = EXCLUDED.nivel_actual,
            promedio_puntaje    = EXCLUDED.promedio_puntaje,
            fecha_ultimo_update = EXCLUDED.fecha_ultimo_update
    """, (id_estudiante, id_competencia, nuevo_nivel, nuevo_score))


def detectar_racha(cursor, id_estudiante, id_competencia, n=3):
    """
    Retorna:
      'positiva' → últimas n respuestas todas correctas → dar ejercicio más difícil
      'negativa' → últimas n respuestas todas incorrectas → dar ejercicio más fácil
      None       → mixto
    Solo considera respuestas en modo 'repaso' para no contaminar con evaluaciones.
    """
    cursor.execute("""
        SELECT op.es_correcta
        FROM respuestas_estudiantes r
        JOIN opciones_ejercicio op ON op.id_opcion = r.id_opcion
        JOIN ejercicios e ON e.id_ejercicio = r.id_ejercicio
        WHERE r.id_estudiante = %s AND e.id_competencia = %s
          AND r.modo = 'repaso'
        ORDER BY r.fecha DESC
        LIMIT %s
    """, (id_estudiante, id_competencia, n))
    rows = cursor.fetchall()
    if len(rows) < n:
        return None
    if all(r["es_correcta"] for r in rows):
        return "positiva"
    if not any(r["es_correcta"] for r in rows):
        return "negativa"
    return None


def predecir_nivel_competencia(cursor, id_estudiante, id_competencia):
    """
    Devuelve el nivel de dificultad a usar ('bajo'/'medio'/'alto')
    basándose en NEC (fuente autoritativa) con ajuste ±1 del modelo ML.
    """
    nivel_actual, _ = leer_nec(cursor, id_estudiante, id_competencia)
    nivel_base = nivel_display_texto(nivel_actual)
    print(f"📋 NEC comp={id_competencia}: nivel_actual={nivel_actual} → base='{nivel_base}'")

    if MODELO_TUTOR is not None:
        X = calcular_features_competencia(cursor, id_estudiante, id_competencia)
        if X is not None:
            try:
                y_pred   = MODELO_TUTOR.predict(X)[0]
                nivel_ml = (ENCODER_NIVEL.inverse_transform([y_pred])[0]
                            if ENCODER_NIVEL else str(y_pred))
                print(f"🤖 ML predijo '{nivel_ml}' est={id_estudiante} comp={id_competencia}")

                _orden   = {"bajo": 0, "medio": 1, "alto": 2}
                _inverso = {0: "bajo", 1: "medio", 2: "alto"}
                base_idx = _orden.get(nivel_base, 0)
                ml_idx   = _orden.get(nivel_ml, base_idx)
                acotado  = min(ml_idx, base_idx + 1)
                nivel_final = _inverso[acotado]
                print(f"🎯 Nivel final (acotado): '{nivel_final}'")
                return nivel_final
            except Exception as e:
                print("Error predicción ML:", e)

    return nivel_base


def actualizar_progreso_estudiante(cursor, id_estudiante):
    """Actualiza progreso_general en tabla estudiante usando la fórmula unificada."""
    cursor.execute("""
        SELECT id_competencia, COALESCE(nivel_actual, 1) AS nivel_actual
        FROM nivel_estudiante_competencia
        WHERE id_estudiante = %s AND id_competencia BETWEEN 1 AND 4
    """, (id_estudiante,))
    rows = cursor.fetchall() or []

    if not rows:
        return

    total_progreso = sum(nivel_to_progreso(r["nivel_actual"]) for r in rows)
    progreso_general = int(round(total_progreso / 4))

    cursor.execute("""
        UPDATE estudiante
        SET progreso_general = %s
        WHERE id_estudiante = %s
    """, (progreso_general, id_estudiante))


# =========================================================
#  GET /tutor/ejercicio_siguiente
# =========================================================
@ws_tutor.route("/ejercicio_siguiente", methods=["GET"])
@jwt_required()
def ejercicio_siguiente():
    id_estudiante = request.args.get("idEstudiante", type=int)
    id_dominio    = request.args.get("idDominio",    type=int)
    ajuste        = request.args.get("ajuste",       type=str)
    modo          = (request.args.get("modo") or "repaso").lower().strip()
    id_evaluacion        = request.args.get("idEvaluacion",      type=int)
    post_refuerzo        = request.args.get("postRefuerzo",      "").lower() == "true"
    id_ejercicio_fallado = request.args.get("idEjercicioFallado", type=int)

    if not id_estudiante:
        return jsonify({"error": "idEstudiante es obligatorio", "status": False}), 400

    con    = Conexion()
    cursor = con.cursor()

    try:
        # ── Verificar que el docente haya asignado el diagnóstico inicial ──
        cursor.execute("""
            SELECT (cantidad IS NULL
                    AND regularidad_equivalencia_cambio IS NULL
                    AND forma_movimiento_localizacion   IS NULL
                    AND gestion_datos_incertidumbre     IS NULL) AS sin_diagnostico
            FROM estudiante
            WHERE id_estudiante = %s
        """, (id_estudiante,))
        row_diag = cursor.fetchone()
        if row_diag and row_diag.get("sin_diagnostico"):
            return jsonify({
                "status":         False,
                "sinEjercicios":  True,
                "bloqueado":      True,
                "mensaje": (
                    "Tu docente aún no ha registrado tu diagnóstico inicial. "
                    "Contacta a tu profesor para que complete tu evaluación y puedas comenzar a practicar."
                ),
            }), 200

        # ── Evaluación: verificar límite y usar ejercicios pre-seleccionados ──
        if modo == "evaluacion" and id_evaluacion:
            cursor.execute("""
                SELECT ev.ejercicios_grupos,
                       ev.num_preguntas,
                       COALESCE(eg.grupo, 'A') AS grupo,
                       COALESCE(er.total_preguntas, 0) AS ya_respondidas
                FROM evaluaciones ev
                LEFT JOIN evaluacion_grupos eg
                       ON eg.id_evaluacion = ev.id_evaluacion
                      AND eg.id_estudiante  = %s
                LEFT JOIN evaluacion_resultados er
                       ON er.id_evaluacion  = ev.id_evaluacion
                      AND er.id_estudiante  = %s
                WHERE ev.id_evaluacion = %s
            """, (id_estudiante, id_estudiante, id_evaluacion))
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

                # Intentar usar ejercicios pre-seleccionados del grupo asignado
                grupos_json = row_ev.get("ejercicios_grupos")
                grupo       = str(row_ev.get("grupo") or "A").upper()
                if grupos_json:
                    try:
                        grupos_dict = json.loads(grupos_json) if isinstance(grupos_json, str) else grupos_json
                        ids_grupo   = [int(x) for x in (grupos_dict.get(grupo) or [])]
                        if ids_grupo:
                            cursor.execute("""
                                SELECT e.id_ejercicio,
                                       e.descripcion  AS enunciado,
                                       e.imagen_url,
                                       e.pista,
                                       COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
                                       c.id_competencia,
                                       c.descripcion  AS competencia
                                FROM ejercicios e
                                JOIN competencias c ON e.id_competencia = c.id_competencia
                                WHERE e.id_ejercicio = ANY(%s)
                                  AND NOT EXISTS (
                                      SELECT 1 FROM respuestas_estudiantes r
                                      WHERE r.id_ejercicio  = e.id_ejercicio
                                        AND r.id_estudiante = %s
                                        AND r.modo          = 'evaluacion'
                                  )
                                  AND EXISTS (
                                      SELECT 1 FROM opciones_ejercicio oe
                                      WHERE oe.id_ejercicio = e.id_ejercicio
                                  )
                                ORDER BY RANDOM()
                                LIMIT 1
                            """, (ids_grupo, id_estudiante))
                            ej_pre = cursor.fetchone()
                            if ej_pre:
                                id_ej_pre   = ej_pre["id_ejercicio"]
                                id_comp_pre = ej_pre["id_competencia"]
                                nivel_pre   = ej_pre["nivel_ejercicio"]

                                imagen_url_pre = None
                                img_bd = ej_pre.get("imagen_url")
                                if img_bd:
                                    if img_bd.startswith(("http://", "https://")):
                                        # URL absoluta (Cloudinary): usar tal cual.
                                        # Antes se le extraía el basename y se
                                        # reconstruía como archivo local → 404.
                                        imagen_url_pre = img_bd
                                    else:
                                        base           = request.host_url.rstrip("/")
                                        nombre         = os.path.basename(img_bd)
                                        imagen_url_pre = f"{base}/ejercicios/imagen/{nombre}"

                                cursor.execute("""
                                    SELECT id_opcion, letra, descripcion
                                    FROM opciones_ejercicio
                                    WHERE id_ejercicio = %s
                                    ORDER BY letra
                                """, (id_ej_pre,))
                                opciones_pre = [
                                    {"idOpcion": o["id_opcion"], "letra": o["letra"], "texto": o["descripcion"]}
                                    for o in cursor.fetchall()
                                ]

                                nivel_nec_pre, _ = leer_nec(cursor, id_estudiante, id_comp_pre)
                                nivel_est_pre    = nivel_display_texto(nivel_nec_pre)

                                print(f"📋 Evaluación: ejercicio pre-seleccionado id={id_ej_pre} grupo={grupo}")
                                return jsonify({
                                    "status":                     True,
                                    "sinEjercicios":              False,
                                    "idEjercicio":                id_ej_pre,
                                    "idCompetencia":              id_comp_pre,
                                    "enunciado":                  ej_pre["enunciado"],
                                    "imagenUrl":                  imagen_url_pre,
                                    "opciones":                   opciones_pre,
                                    "pista":                      None,
                                    "modo":                       modo,
                                    "nivelEjercicio":             nivel_pre,
                                    "nivelEstudianteCompetencia": nivel_est_pre,
                                    "mensaje":                    None,
                                }), 200
                    except Exception as e_grupo:
                        print(f"⚠️ Error leyendo ejercicios_grupos: {e_grupo}")
                # Sin pre-selección → caer en selección aleatoria normal

        where  = []
        params = []

        if id_dominio:
            where.append("e.id_competencia = %s")
            params.append(id_dominio)

        # ── Selección de dificultad ───────────────────────────────────────
        if post_refuerzo:
            # Verificación post-refuerzo: misma competencia, un nivel más fácil
            if id_dominio:
                nivel_base_ver, _ = leer_nec(cursor, id_estudiante, id_dominio)
            else:
                cursor.execute("""
                    SELECT COALESCE(ROUND(AVG(nivel_actual))::int, 1) AS nivel_min
                    FROM nivel_estudiante_competencia
                    WHERE id_estudiante = %s AND id_competencia BETWEEN 1 AND 4
                """, (id_estudiante,))
                nivel_base_ver = int((cursor.fetchone() or {}).get("nivel_min") or 1)

            nivel_ver   = max(1, nivel_base_ver - 1)
            nivel_where = NIVEL_EJERCICIO_WHERE.get(nivel_ver, f"{DIFICULTAD_SQL} <= 3")
            where.append(nivel_where)
            print(f"🔍 postRefuerzo: base={nivel_base_ver} → nivel_ver={nivel_ver} filtro={nivel_where}")
        elif ajuste in ("mas_dificil", "mas_facil"):
            # Leer NEC para ajuste relativo al nivel real del estudiante
            if id_dominio:
                nivel_base_ajuste, _ = leer_nec(cursor, id_estudiante, id_dominio)
            else:
                cursor.execute("""
                    SELECT COALESCE(ROUND(AVG(nivel_actual))::int, 1) AS nivel_min
                    FROM nivel_estudiante_competencia
                    WHERE id_estudiante = %s AND id_competencia BETWEEN 1 AND 4
                """, (id_estudiante,))
                nivel_base_ajuste = int((cursor.fetchone() or {}).get("nivel_min") or 1)

            nivel_adj = (min(7, nivel_base_ajuste + 1) if ajuste == "mas_dificil"
                         else max(1, nivel_base_ajuste - 1))
            nivel_where = NIVEL_EJERCICIO_WHERE.get(nivel_adj, f"{DIFICULTAD_SQL} <= 3")
            where.append(nivel_where)
            print(f"⚙️ ajuste='{ajuste}' base={nivel_base_ajuste} → nivel_adj={nivel_adj} filtro={nivel_where}")
        else:
            # 1) Determinar nivel base desde NEC + predicción ML
            if id_dominio:
                nivel_actual_int, _ = leer_nec(cursor, id_estudiante, id_dominio)
                nivel_predicho_texto = predecir_nivel_competencia(
                    cursor, id_estudiante, id_dominio
                )
            else:
                cursor.execute("""
                    SELECT COALESCE(ROUND(AVG(nivel_actual))::int, 1) AS nivel_min
                    FROM nivel_estudiante_competencia
                    WHERE id_estudiante = %s AND id_competencia BETWEEN 1 AND 4
                """, (id_estudiante,))
                row_min = cursor.fetchone() or {}
                nivel_actual_int = int(row_min.get("nivel_min") or 1)
                nivel_predicho_texto = nivel_display_texto(nivel_actual_int)
                print(f"📊 Nivel global mínimo={nivel_actual_int} → '{nivel_predicho_texto}'")

            # 2) Ajuste ML conservando la granularidad del NEC (1-7):
            #    si el ML ubica al alumno en una banda distinta a la de su NEC,
            #    desplaza UN nivel; si coincide, mantiene el nivel exacto.
            #    (Antes se colapsaba a 1/3/5 y un alumno NEC=4 filtraba como 3.)
            _ORDEN_BANDA = {"bajo": 0, "medio": 1, "alto": 2}
            banda_nec = _ORDEN_BANDA.get(nivel_display_texto(nivel_actual_int), 0)
            banda_ml  = _ORDEN_BANDA.get(nivel_predicho_texto, banda_nec)
            if banda_ml > banda_nec:
                nivel_para_ejercicio = min(7, nivel_actual_int + 1)
                ajuste_ml = +1
            elif banda_ml < banda_nec:
                nivel_para_ejercicio = max(1, nivel_actual_int - 1)
                ajuste_ml = -1
            else:
                nivel_para_ejercicio = nivel_actual_int
                ajuste_ml = 0

            # 3) Ajuste por racha. Si el ML ya desplazó en la misma dirección,
            #    la racha NO suma un segundo nivel para evitar saltos de +2 con
            #    banco de ejercicios pequeño. Solo actúa cuando el ML no desplazó.
            if id_dominio:
                racha = detectar_racha(cursor, id_estudiante, id_dominio)
                if racha == "positiva" and ajuste_ml <= 0:
                    nivel_para_ejercicio = min(7, nivel_para_ejercicio + 1)
                    print(f"🔥 Racha positiva → nivel_ejercicio={nivel_para_ejercicio}")
                elif racha == "negativa" and ajuste_ml >= 0:
                    nivel_para_ejercicio = max(1, nivel_para_ejercicio - 1)
                    print(f"❄️ Racha negativa → nivel_ejercicio={nivel_para_ejercicio}")

            nivel_where = NIVEL_EJERCICIO_WHERE.get(nivel_para_ejercicio, f"{DIFICULTAD_SQL} <= 3")
            where.append(nivel_where)
            print(f"🎯 ML='{nivel_predicho_texto}'→{nivel_para_ejercicio} | Filtro: {nivel_where}")

        # ── Excluir el ejercicio que causó el refuerzo (evita repetirlo en verificación) ──
        if post_refuerzo and id_ejercicio_fallado:
            where.append("e.id_ejercicio != %s")
            params.append(id_ejercicio_fallado)

        # ── Excluir ejercicios ya respondidos ─────────────────────────────
        if modo == "evaluacion":
            # En evaluación cada pregunta se responde UNA sola vez
            where.append("""
                NOT EXISTS(
                    SELECT 1 FROM respuestas_estudiantes r
                    WHERE r.id_ejercicio  = e.id_ejercicio
                      AND r.id_estudiante = %s
                      AND r.modo          = 'evaluacion'
                )
            """)
        else:
            # Repetición espaciada: solo se excluyen los ejercicios ya
            # respondidos CORRECTAMENTE en repaso. Los fallados vuelven a
            # estar disponibles para verificar que el alumno ya domina el
            # concepto (antes un ejercicio fallado no volvía a salir nunca).
            where.append("""
                NOT EXISTS(
                    SELECT 1 FROM respuestas_estudiantes r
                    JOIN opciones_ejercicio op_r ON op_r.id_opcion = r.id_opcion
                    WHERE r.id_ejercicio  = e.id_ejercicio
                      AND r.id_estudiante = %s
                      AND r.modo          = 'repaso'
                      AND op_r.es_correcta
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

        # En repaso: priorizar ejercicios NUNCA intentados; los fallados
        # (disponibles por la repetición espaciada) salen cuando se agota
        # el contenido nuevo del nivel.
        orden_sql   = "ORDER BY RANDOM()"
        params_main = list(params)
        if modo != "evaluacion":
            orden_sql = """
                ORDER BY EXISTS(
                    SELECT 1 FROM respuestas_estudiantes r2
                    WHERE r2.id_ejercicio  = e.id_ejercicio
                      AND r2.id_estudiante = %s
                      AND r2.modo          = 'repaso'
                ) ASC, RANDOM()
            """
            params_main.append(id_estudiante)

        cursor.execute(f"""
            SELECT e.id_ejercicio,
                   e.descripcion  AS enunciado,
                   e.imagen_url,
                   e.pista,
                   COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
                   c.id_competencia,
                   c.descripcion  AS competencia
            FROM ejercicios e
            JOIN competencias c ON e.id_competencia = c.id_competencia
            {where_clause}
            {orden_sql}
            LIMIT 1
        """, tuple(params_main))

        ejercicio = cursor.fetchone()

        # Fallback 1 (solo repaso): misma dificultad, permite repetir ejercicios ya respondidos
        if not ejercicio and modo != "evaluacion":
            print("⚠️ Ejercicios del nivel agotados. Permitiendo repetición en repaso...")
            params_sin_exists = params[:-1]  # eliminar el id_estudiante del NOT EXISTS
            where_sin_exists  = [w for w in where if "NOT EXISTS" not in w]
            wc_sin_exists = ("WHERE " + " AND ".join(where_sin_exists)) if where_sin_exists else ""
            cursor.execute(f"""
                SELECT e.id_ejercicio,
                       e.descripcion  AS enunciado,
                       e.imagen_url,
                       e.pista,
                       COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
                       c.id_competencia,
                       c.descripcion  AS competencia
                FROM ejercicios e
                JOIN competencias c ON e.id_competencia = c.id_competencia
                {wc_sin_exists}
                ORDER BY RANDOM()
                LIMIT 1
            """, tuple(params_sin_exists))
            ejercicio = cursor.fetchone()

        # Fallback 2: cualquier dificultad, sin repetir (mantiene filtro de competencia)
        if not ejercicio:
            print("⚠️ Sin ejercicios del nivel predicho. Intentando sin filtro de nivel...")
            where_sin_nivel  = [w for w in where if "e.nivel" not in w]
            where_clause_sin = ("WHERE " + " AND ".join(where_sin_nivel) if where_sin_nivel else "")

            cursor.execute(f"""
                SELECT e.id_ejercicio,
                       e.descripcion  AS enunciado,
                       e.imagen_url,
                       e.pista,
                       COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
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

        # Nivel del estudiante para esta competencia (para mostrar en UI)
        nivel_nec_ej, _     = leer_nec(cursor, id_estudiante, id_competencia)
        nivel_est_competencia = nivel_display_texto(nivel_nec_ej)

        imagen_url_bd = ejercicio.get("imagen_url")
        if imagen_url_bd:
            if imagen_url_bd.startswith(("http://", "https://")):
                # URL absoluta (Cloudinary): usar tal cual. Antes se le extraía
                # el basename y se reconstruía como archivo local → 404.
                imagen_url = imagen_url_bd
            else:
                base       = request.host_url.rstrip("/")
                nombre     = os.path.basename(imagen_url_bd)
                imagen_url = f"{base}/ejercicios/imagen/{nombre}"
        else:
            imagen_url = None

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
            "status":                     True,
            "sinEjercicios":              False,
            "idEjercicio":                id_ejercicio,
            "idCompetencia":              id_competencia,
            "enunciado":                  ejercicio["enunciado"],
            "imagenUrl":                  imagen_url,
            "opciones":                   opciones,
            "pista":                      pista,
            "modo":                       modo,
            "nivelEjercicio":             nivel_ej,
            "nivelEstudianteCompetencia": nivel_est_competencia,
            "mensaje":                    None,
            "esVerificacion":             post_refuerzo,
        }), 200

    except Exception as e:
        print("ERROR en ejercicio_siguiente:", e)
        return jsonify({"status": False, "error": str(e)}), 500

    finally:
        try:
            con.commit()   # persiste el INSERT de NEC hecho por leer_nec()
        except Exception:
            pass
        cursor.close()
        con.close()


# =========================================================
#  POST /tutor/responder
# =========================================================
@ws_tutor.route("/responder", methods=["POST"])
@jwt_required()
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
                   COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
                   e.pista
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
        pista_ejercicio = (row.get("pista") or "").strip()

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

        # 3) ── NÚCLEO: leer NEC ────────────────────────────────────────────
        nivel_actual_bd, score_actual = leer_nec(cursor, id_estudiante, id_competencia)

        # 4) Progreso (registro de actividad — siempre, independiente del modo)
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

        # uso_pista reduce el delta positivo: acertar con ayuda avanza menos
        delta       = calcular_delta(es_correcta, tiempo_respuesta, nivel_ejercicio,
                                     uso_pista=uso_pista and es_repaso)
        nuevo_score = max(0.0, min(100.0, score_actual + delta))
        nuevo_nivel = score_to_nivel(nuevo_score)

        if es_repaso:
            # 5a) Puntaje binario → SOLO repaso alimenta el historial del ML.
            #     Evaluación es medición, no entrenamiento: no debe contaminar puntajes.
            puntaje_bin = 100 if es_correcta else 0
            cursor.execute("""
                INSERT INTO puntajes (puntaje, fecha_registro, id_competencia, id_estudiante)
                VALUES (%s, NOW(), %s, %s)
            """, (puntaje_bin, id_competencia, id_estudiante))
            # 5b) Actualizar nivel adaptativo del alumno
            guardar_nec(cursor, id_estudiante, id_competencia, nuevo_score, nuevo_nivel)
            print(f"📈 NEC comp={id_competencia}: {score_actual:.1f}{delta:+d}={nuevo_score:.1f} → nivel {nuevo_nivel}")
        else:
            # Evaluación: el NEC no se modifica; usamos el nivel real para la respuesta
            nuevo_nivel = nivel_actual_bd
            nuevo_score = score_actual
            print(f"📊 Evaluación comp={id_competencia}: NEC sin cambio, nivel={nivel_actual_bd}")

        # Determinar ajuste y mensaje
        if es_correcta:
            if nuevo_nivel > nivel_actual_bd:
                nuevo_ajuste = "mas_dificil"
                mensaje = f"¡Subiste al nivel {NIVEL_NOMBRE.get(nuevo_nivel, str(nuevo_nivel))}!"
            else:
                nuevo_ajuste = "igual"
                mensaje = "¡Correcto! Sigue practicando."
            mostrar_pista = False
        else:
            if nuevo_nivel < nivel_actual_bd:
                nuevo_ajuste = "mas_facil"
                mensaje = "Ajustamos la dificultad para reforzar."
            else:
                nuevo_ajuste = "igual"
                mensaje = "Sigue intentando, puedes lograrlo."
            # Si ya está en N1 (mínimo posible) y tiene racha negativa (≥3 fallos seguidos)
            # devolvemos "mas_facil" para que la app sepa que está atascado en el nivel base
            if nuevo_nivel == 1 and nuevo_ajuste == "igual" and es_repaso:
                racha_n1 = detectar_racha(cursor, id_estudiante, id_competencia, n=3)
                if racha_n1 == "negativa":
                    nuevo_ajuste = "mas_facil"
                    mensaje = "Repasa los materiales de apoyo. ¡Toma tu tiempo!"
            mostrar_pista = es_repaso and bool(pista_ejercicio)

        # Nivel global (promedio de las 4 competencias)
        cursor.execute("""
            SELECT COALESCE(AVG(nivel_actual), 1) AS prom
            FROM nivel_estudiante_competencia
            WHERE id_estudiante = %s AND id_competencia BETWEEN 1 AND 4
        """, (id_estudiante,))
        prom_g             = float((cursor.fetchone() or {}).get("prom") or 1)
        nivel_global_texto = "bajo" if prom_g < 3 else "medio" if prom_g < 5 else "alto"

        nivel_display_str = nivel_display_texto(nuevo_nivel)

        # 6) Progreso general del estudiante (solo repaso actualiza NEC y progreso)
        if es_repaso:
            actualizar_progreso_estudiante(cursor, id_estudiante)

        # 7) Evaluación oficial
        if not es_repaso and id_evaluacion:
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

        # 8) Material sugerido + recursos de búsqueda (solo repaso + respuesta incorrecta)
        material_sugerido    = None
        recursos_adicionales = None
        if es_repaso and not es_correcta:
            try:
                nivel_mat = 1 if nuevo_nivel <= 2 else (2 if nuevo_nivel <= 4 else 3)

                # ── Palabras clave del ejercicio (puestas por el docente) ────────
                cursor.execute(
                    "SELECT palabras_clave FROM ejercicios WHERE id_ejercicio = %s",
                    (id_ejercicio,)
                )
                ej_row     = cursor.fetchone() or {}
                palabras_clave = (ej_row.get("palabras_clave") or "").strip()

                # Si el docente no llenó el campo, usamos términos fijos por competencia
                if not palabras_clave:
                    _KW_COMP = {
                        1: "operaciones numéricas álgebra primaria",
                        2: "ecuaciones algebraicas patrones álgebra",
                        3: "geometría figuras movimiento espacial",
                        4: "estadística datos gráficos probabilidad",
                    }
                    palabras_clave = _KW_COMP.get(id_competencia, "matemáticas álgebra")

                # ── Capa 1: material específico enlazado al ejercicio ────────────
                cursor.execute("""
                    SELECT id_material, titulo, tipo, url
                    FROM material_estudio
                    WHERE id_ejercicio = %s
                    ORDER BY RANDOM() LIMIT 1
                """, (id_ejercicio,))
                mat = cursor.fetchone()

                # ── Capa 2 (fallback): material genérico de la competencia ───────
                if not mat:
                    cursor.execute("""
                        SELECT id_material, titulo, tipo, url
                        FROM material_estudio
                        WHERE id_competencia = %s
                          AND nivel <= %s
                          AND (id_ejercicio IS NULL OR id_ejercicio = 0)
                        ORDER BY RANDOM() LIMIT 1
                    """, (id_competencia, nivel_mat))
                    mat = cursor.fetchone()

                if mat:
                    material_sugerido = {
                        "idMaterial": mat["id_material"],
                        "titulo":     mat["titulo"],
                        "tipo":       mat["tipo"],
                        "url":        mat["url"],
                    }

                # ── URLs de búsqueda (YouTube · Web · PDF) ───────────────────────
                # Se construyen con los términos conceptuales, NO con el enunciado
                q_yt  = urllib.parse.quote_plus(palabras_clave + " matemáticas")
                q_web = urllib.parse.quote_plus(
                    palabras_clave + " matemáticas ejercicio resuelto"
                )
                q_pdf = urllib.parse.quote_plus(
                    palabras_clave + " matemáticas recurso educativo filetype:pdf"
                )
                recursos_adicionales = {
                    "youtubeUrl": f"https://www.youtube.com/results?search_query={q_yt}",
                    "webUrl":     f"https://www.google.com/search?q={q_web}",
                    "pdfUrl":     f"https://www.google.com/search?q={q_pdf}",
                    "query":      palabras_clave,
                }

            except Exception as e_mat:
                print("Error buscando material/recursos:", e_mat)

        # 9) Detectar 3 fallos consecutivos en la misma competencia → alerta al docente
        docente_alertado = False
        if es_repaso and not es_correcta:
            try:
                cursor.execute("""
                    WITH ultimas AS (
                        SELECT op2.es_correcta
                        FROM respuestas_estudiantes r2
                        JOIN opciones_ejercicio op2 ON op2.id_opcion  = r2.id_opcion
                        JOIN ejercicios e2           ON e2.id_ejercicio = r2.id_ejercicio
                        WHERE r2.id_estudiante = %s
                          AND e2.id_competencia = %s
                          AND r2.modo = 'repaso'
                        ORDER BY r2.fecha DESC
                        LIMIT 3
                    )
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN NOT es_correcta THEN 1 ELSE 0 END) AS incorrectas
                    FROM ultimas
                """, (id_estudiante, id_competencia))
                row_al       = cursor.fetchone() or {}
                total_ul     = int(row_al.get("total") or 0)
                incorrectas_ul = int(row_al.get("incorrectas") or 0)
                if total_ul >= 3 and incorrectas_ul >= 3:
                    docente_alertado = True
                    print(f"🔔 ALERTA DOCENTE: est={id_estudiante} comp={id_competencia} — 3 fallos consecutivos")
            except Exception as e_al:
                print("Error detectando alerta docente:", e_al)

        con.commit()

        return jsonify({
            "correcta":             es_correcta,
            "mostrarPista":         mostrar_pista,
            "mensaje":              mensaje,
            "nuevoAjuste":          nuevo_ajuste,
            "idRespuesta":          id_respuesta,
            "modo":                 modo,
            "nivelMLCompetencia":   nivel_display_str,
            "nivelCompetenciaInt":  nuevo_nivel,
            "scoreCompetencia":     round(nuevo_score, 1),
            "nivelGlobal":          nivel_global_texto,
            "materialSugerido":     material_sugerido,
            "recursosAdicionales":  recursos_adicionales,
            "docenteAlertado":      docente_alertado,
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
_ALLOWED_DESARROLLO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
_MAX_DESARROLLO_BYTES   = 10 * 1024 * 1024  # 10 MB


@ws_tutor.route("/subir_desarrollo", methods=["POST"])
@jwt_required()
def subir_desarrollo():
    id_respuesta = request.form.get("idRespuesta", type=int)
    archivo      = request.files.get("archivo")

    if not id_respuesta or not archivo:
        return jsonify({"status": False, "message": "idRespuesta y archivo son obligatorios"}), 400

    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in _ALLOWED_DESARROLLO_EXT:
        return jsonify({
            "status":  False,
            "message": "Tipo de archivo no permitido. Solo se aceptan imágenes (jpg, png, gif, webp) y PDF.",
        }), 400

    # Verificar tamaño sin cargar el archivo completo en memoria
    archivo.seek(0, 2)
    size = archivo.tell()
    archivo.seek(0)
    if size > _MAX_DESARROLLO_BYTES:
        return jsonify({
            "status":  False,
            "message": "El archivo supera el tamaño máximo permitido (10 MB).",
        }), 400

    filename    = secure_filename(f"resp_{id_respuesta}{ext}")
    ruta_fisica = os.path.join(DESARROLLOS_FOLDER, filename)

    try:
        # ── Subida a Cloudinary (Railway) o filesystem (local) ──────────
        from util_cloudinary import cloudinary_configurado, subir_imagen
        if cloudinary_configurado():
            public_id = f"tutormath/desarrollos/resp_{id_respuesta}"
            url_abs   = subir_imagen(archivo, public_id)
        else:
            # Modo local: guardar en disco
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


# =========================================================
#  GET /tutor/nivel_actual
# =========================================================
@ws_tutor.route("/nivel_actual", methods=["GET"])
@jwt_required()
def nivel_actual():
    id_estudiante  = request.args.get("idEstudiante",  type=int)
    id_competencia = request.args.get("idCompetencia", type=int)

    if not id_estudiante or not id_competencia:
        return jsonify({"status": False, "error": "idEstudiante e idCompetencia son obligatorios"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        nivel_int, score = leer_nec(cursor, id_estudiante, id_competencia)
        nivel_ml         = nivel_display_texto(nivel_int)
        con.commit()  # guarda init si fue necesario

        return jsonify({
            "status":          True,
            "idEstudiante":    id_estudiante,
            "idCompetencia":   id_competencia,
            "nivelML":         nivel_ml,
            "nivelActual":     nivel_int,
            "scoreActual":     round(score, 1),
            "progresoActual":  nivel_to_progreso(nivel_int),
            "totalIntentos":   0,
            "promedioPuntaje": round(score, 1),
        }), 200

    except Exception as e:
        con.rollback()
        return jsonify({"status": False, "error": str(e)}), 500
    finally:
        cursor.close()
        con.close()


# =========================================================
#  GET /tutor/sugerencias/<id_est>/<id_comp>
# =========================================================
@ws_tutor.route("/sugerencias/<int:id_estudiante>/<int:id_competencia>", methods=["GET"])
@jwt_required()
def sugerencias_ejercicios(id_estudiante: int, id_competencia: int):
    limite = request.args.get("limite", default=5, type=int)
    con    = Conexion()
    cursor = con.cursor()

    try:
        nivel_ml = predecir_nivel_competencia(cursor, id_estudiante, id_competencia)

        # Usar los mismos umbrales que ejercicio_siguiente() para consistencia
        _MAP = {"bajo": 1, "medio": 3, "alto": 5}
        nivel_int = _MAP.get(nivel_ml, 1)
        filtro = "AND " + NIVEL_EJERCICIO_WHERE.get(nivel_int, f"{DIFICULTAD_SQL} <= 3")

        cursor.execute(f"""
            SELECT e.id_ejercicio,
                   e.descripcion  AS enunciado,
                   e.imagen_url,
                   COALESCE(e.nivel_logro, e.nivel, 1) AS nivel_ejercicio,
                   c.id_competencia,
                   c.descripcion  AS competencia
            FROM ejercicios e
            JOIN competencias c ON e.id_competencia = c.id_competencia
            WHERE e.id_competencia = %s
              AND NOT EXISTS (
                SELECT 1 FROM respuestas_estudiantes r
                JOIN opciones_ejercicio op_r ON op_r.id_opcion = r.id_opcion
                WHERE r.id_ejercicio  = e.id_ejercicio
                  AND r.id_estudiante = %s
                  AND r.modo          = 'repaso'
                  AND op_r.es_correcta
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
@jwt_required()
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
@jwt_required()
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
# =========================================================
@ws_tutor.route("/material/abrir", methods=["POST"])
@jwt_required()
def registrar_apertura_material():
    data          = request.get_json() or {}
    id_estudiante = data.get("idEstudiante")
    id_material   = data.get("idMaterial")

    if not id_estudiante or not id_material:
        return jsonify({"ok": False, "error": "Faltan parámetros"}), 400

    con    = Conexion()
    cursor = con.cursor()
    try:
        cursor.execute("""
            INSERT INTO historial_material_estudio
                (id_estudiante, id_material, estado, veces_revisado, fecha_acceso)
            VALUES (%s, %s, 'visto', 1, NOW())
            ON CONFLICT (id_estudiante, id_material)
            DO UPDATE SET
                estado         = CASE
                                   WHEN historial_material_estudio.estado = 'completado' THEN 'completado'
                                   ELSE 'visto'
                                 END,
                veces_revisado = historial_material_estudio.veces_revisado + 1,
                fecha_acceso   = NOW()
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
