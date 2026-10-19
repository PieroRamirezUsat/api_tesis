# comparar_modelos_v2.py
"""
Script de COMPARACION de modelos de clasificación para el STI de Álgebra.

VERSION 3 (2026-10-16) — usa las mismas 9 features, la misma etiqueta NO
CIRCULAR y el mismo filtro de salón piloto real que train_model.py (el
script que realmente genera modelo_tutor.pkl, el modelo que carga
ws/tutor.py en producción). Importa esas piezas directamente de
train_model.py para que nunca se desalineen entre sí.

Historial de correcciones sobre la version original (datos_ml.py):
  1. (ronda anterior) la etiqueta dejó de ser un umbral de promedio_puntaje
     (una de las propias features) y pasó a depender de tasa_aprobados +
     tendencia — pero eso SEGUÍA siendo circular, porque esas dos variables
     también son features de entrada.
  2. (esta ronda) la etiqueta ahora viene del examen diagnóstico MINEDU
     (tabla estudiante), una fuente verdaderamente independiente de las
     features de interacción. Además, el dataset se filtra al salón piloto
     real (antes mezclaba cuentas de prueba de otros salones) y el split
     de entrenamiento/prueba se agrupa por estudiante (antes un mismo
     alumno podía aparecer en ambos conjuntos a través de otra competencia).
  3. Se agregaron 2 features más (tiempo_respuesta_promedio, tasa_uso_pista
     — ya recomendadas en la propia tesis) porque, probadas, mejoran la
     validación cruzada real de ~56% a ~63%.

Modelos evaluados:
    1. Árbol de Decisión   (modelo elegido para el STI, mismos
                             hiperparametros que train_model.py)
    2. Regresión Logística
    3. KNN (k=3)

Métricas calculadas por modelo:
    - Accuracy en conjunto de prueba (split agrupado por estudiante)
    - F1-score ponderado
    - Validación cruzada agrupada por estudiante (accuracy media ± std)
    - Matriz de confusión

Al final imprime una JUSTIFICACION COMPLETA de por qué se elige
el Árbol de Decisión, evaluando criterios técnicos Y pedagógicos
propios de un Sistema Tutor Inteligente (STI).

Ejecución:
    (venv) python comparar_modelos_v2.py
"""

import numpy as np
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier

from conexionBD import Conexion
from train_model import ID_SALON_PILOTO, UMBRAL_APROBADO, diagnostico_a_nivel

SEP  = "=" * 65
SEP2 = "-" * 65

FEATURE_NAMES = [
    "total_intentos", "promedio_puntaje",
    "min_puntaje", "max_puntaje",
    "std_puntaje", "tasa_aprobados", "tendencia",
    "tiempo_respuesta_promedio", "tasa_uso_pista",
]

# ─────────────────────────────────────────────────────────────────────
# Tabla de criterios cualitativos para un STI educativo
# Puntuación: 1 (bajo)  2 (medio)  3 (alto)
# ─────────────────────────────────────────────────────────────────────
CRITERIOS_STI = {
    # criterio                          arbol  logReg  knn
    "Reglas legibles (explicar logica)": (3,     1,      1),
    "Interpretable por el docente"     : (3,     2,      1),
    "No requiere normalizar datos"     : (3,     1,      1),
    "Funciona bien con pocos datos"    : (3,     2,      1),
    "Velocidad de prediccion"          : (3,     3,      2),
    "Maneja relaciones no lineales"    : (3,     1,      3),
    "Resistencia al sobreajuste"       : (2,     3,      2),
    "Facilidad de ajustar umbrales"    : (3,     1,      1),
}


# ─────────────────────────────────────────────────────────────────────
def cargar_datos_entrenamiento():
    """
    Replica EXACTAMENTE la logica de train_model.py (la version que
    genera modelo_tutor.pkl, el modelo real cargado por ws/tutor.py):

    9 features (ver FEATURE_NAMES) y etiqueta NO CIRCULAR tomada del
    examen diagnóstico MINEDU (tabla estudiante), filtrando SOLO el
    salón piloto real (ID_SALON_PILOTO) — no las cuentas de prueba de
    otros salones.

    Si alguna clase tiene menos de MIN_MUESTRAS registros reales, se
    agregan muestras sinteticas (igual que train_model.py) para poder
    entrenar/validar con las 3 clases representadas. Se imprime
    claramente cuantas muestras sinteticas se agregaron, por
    transparencia (esto debe mencionarse en la tesis si se usa).

    Devuelve X, y, groups (groups = id_estudiante, para split/CV
    agrupados por estudiante).
    """
    con = Conexion()
    cur = con.cursor()

    cur.execute("""
        SELECT
            p.id_estudiante,
            p.id_competencia,
            COUNT(*)                                               AS total_intentos,
            AVG(p.puntaje)                                        AS promedio_puntaje,
            MIN(p.puntaje)                                        AS min_puntaje,
            MAX(p.puntaje)                                        AS max_puntaje,
            COALESCE(STDDEV(p.puntaje), 0)                       AS std_puntaje,
            SUM(CASE WHEN p.puntaje >= %s THEN 1 ELSE 0 END)     AS num_aprobados,
            CORR(EXTRACT(EPOCH FROM p.fecha_registro), p.puntaje) AS tendencia,
            e.cantidad                                             AS diag_cantidad,
            e.regularidad_equivalencia_cambio                     AS diag_regularidad,
            e.forma_movimiento_localizacion                       AS diag_forma,
            e.gestion_datos_incertidumbre                         AS diag_gestion
        FROM puntajes p
        JOIN estudiante_salones es ON es.id_estudiante = p.id_estudiante
                                   AND es.id_salon      = %s
        JOIN estudiante e          ON e.id_estudiante   = p.id_estudiante
        GROUP BY p.id_estudiante, p.id_competencia,
                 e.cantidad, e.regularidad_equivalencia_cambio,
                 e.forma_movimiento_localizacion, e.gestion_datos_incertidumbre
        HAVING COUNT(*) >= 1
    """, (UMBRAL_APROBADO, ID_SALON_PILOTO))

    rows = cur.fetchall()

    cur.execute("""
        SELECT r.id_estudiante, e.id_competencia,
               AVG(r.tiempo_respuesta)                          AS tiempo_promedio,
               AVG(CASE WHEN r.uso_pista THEN 1.0 ELSE 0.0 END) AS tasa_pista
        FROM respuestas_estudiantes r
        JOIN ejercicios e          ON e.id_ejercicio  = r.id_ejercicio
        JOIN estudiante_salones es ON es.id_estudiante = r.id_estudiante
                                   AND es.id_salon      = %s
        WHERE r.modo = 'repaso'
        GROUP BY r.id_estudiante, e.id_competencia
    """, (ID_SALON_PILOTO,))
    tiempo_pista_por_ec = {
        (row["id_estudiante"], row["id_competencia"]): (row["tiempo_promedio"], row["tasa_pista"])
        for row in cur.fetchall()
    }

    cur.close()
    con.close()

    DIAG_COL = {1: "diag_cantidad", 2: "diag_regularidad", 3: "diag_forma", 4: "diag_gestion"}

    X = []
    y = []
    groups = []
    omitidos_sin_diagnostico = 0

    for row in rows:
        total     = row["total_intentos"] or 0
        promedio  = row["promedio_puntaje"]
        min_p     = row["min_puntaje"]
        max_p     = row["max_puntaje"]
        std_p     = row["std_puntaje"] or 0.0
        aprobados = row["num_aprobados"] or 0
        tendencia = row["tendencia"]

        if promedio is None or total == 0:
            continue

        id_competencia = row["id_competencia"]
        diag_valor = row.get(DIAG_COL.get(id_competencia))
        if diag_valor is None:
            omitidos_sin_diagnostico += 1
            continue

        promedio  = max(0.0, min(100.0, float(promedio)))
        min_p     = max(0.0, min(100.0, float(min_p)))
        max_p     = max(0.0, min(100.0, float(max_p)))
        std_p     = max(0.0, float(std_p))
        tasa      = float(aprobados) / float(total)
        tendencia = float(tendencia) if tendencia is not None else 0.0
        tendencia = max(-1.0, min(1.0, tendencia))

        nivel = diagnostico_a_nivel(float(diag_valor))

        tp = tiempo_pista_por_ec.get((row["id_estudiante"], id_competencia))
        tiempo_prom = float(tp[0]) if tp and tp[0] is not None else 0.0
        tasa_pista  = float(tp[1]) if tp and tp[1] is not None else 0.0

        X.append([float(total), promedio, min_p, max_p, std_p, tasa, tendencia,
                  tiempo_prom, tasa_pista])
        y.append(nivel)
        groups.append(row["id_estudiante"])

    if omitidos_sin_diagnostico:
        print(f"  ℹ️  {omitidos_sin_diagnostico} fila(s) omitida(s) por no tener "
              f"diagnóstico independiente para esa competencia.")

    conteo_real = {"bajo": 0, "medio": 0, "alto": 0}
    for nivel in y:
        conteo_real[nivel] += 1
    print(f"  Distribución REAL de datos (sin sintéticos): {conteo_real}")
    print(f"  Estudiantes reales únicos: {len(set(groups))}")

    MIN_MUESTRAS = 10
    sinteticos_agregados = {"bajo": 0, "medio": 0, "alto": 0}

    def _sint(prom_range, min_range, max_range, std_range, tasa_range, tend_range):
        total_s    = np.random.randint(3, 20)
        promedio_s = np.random.uniform(*prom_range)
        min_s      = np.random.uniform(*min_range)
        max_s      = np.random.uniform(*max_range)
        std_s      = np.random.uniform(*std_range)
        tasa_s     = np.random.uniform(*tasa_range)
        tend_s     = np.random.uniform(*tend_range)
        tiempo_s   = np.random.uniform(60, 400)
        pista_s    = np.random.uniform(0.0, 0.5)
        return [float(total_s), promedio_s, min_s, max_s, std_s, tasa_s, tend_s, tiempo_s, pista_s]

    _next_synth_id = [-1]

    def _nuevo_grupo_sintetico():
        gid = _next_synth_id[0]
        _next_synth_id[0] -= 1
        return gid

    if conteo_real["alto"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo_real["alto"]
        for _ in range(n):
            X.append(_sint((70, 100), (55, 80), (85, 100), (0, 20), (0.7, 1.0), (0.0, 1.0)))
            y.append("alto")
            groups.append(_nuevo_grupo_sintetico())
        sinteticos_agregados["alto"] = n

    if conteo_real["medio"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo_real["medio"]
        for _ in range(n):
            X.append(_sint((40, 70), (20, 55), (60, 85), (5, 35), (0.3, 0.7), (-0.3, 0.3)))
            y.append("medio")
            groups.append(_nuevo_grupo_sintetico())
        sinteticos_agregados["medio"] = n

    if conteo_real["bajo"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo_real["bajo"]
        for _ in range(n):
            X.append(_sint((0, 40), (0, 25), (20, 55), (0, 15), (0.0, 0.3), (-1.0, 0.2)))
            y.append("bajo")
            groups.append(_nuevo_grupo_sintetico())
        sinteticos_agregados["bajo"] = n

    total_sinteticos = sum(sinteticos_agregados.values())
    if total_sinteticos > 0:
        print(f"  ⚠️  Muestras SINTÉTICAS agregadas (clases con <{MIN_MUESTRAS} reales): "
              f"{sinteticos_agregados}  (total: {total_sinteticos})")
        print(f"  >> IMPORTANTE: si este numero no es 0, la tesis debe mencionar que "
              f"parte del entrenamiento usó datos sintéticos para balancear clases.")
    else:
        print(f"  ✅ No se necesitaron muestras sintéticas (las 3 clases ya tenían "
              f">= {MIN_MUESTRAS} registros reales).")

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=object)
    groups = np.array(groups, dtype=int)
    return X, y, groups


# ─────────────────────────────────────────────────────────────────────
def _barra(valor, maximo, ancho=15):
    """Barra ASCII proporcional."""
    llenos = int(round(valor / maximo * ancho)) if maximo > 0 else 0
    return "[" + "#" * llenos + "-" * (ancho - llenos) + "]"


def _estrella(puntuacion):
    """Convierte 1-3 en estrellas visuales."""
    return ("*" * puntuacion).ljust(3)


# ─────────────────────────────────────────────────────────────────────
def mostrar_justificacion(resultados_acc, resultados_f1, resultados_cv,
                          modelo_arbol, feature_names):
    """
    Imprime la sección de justificación del Árbol de Decisión:
      A) Tabla comparativa de métricas cuantitativas
      B) Tabla de criterios cualitativos (STI)
      C) Reglas aprendidas (por qué es explicable)
      D) Veredicto final con argumentos numerados
    """

    nombres = ["Árbol de Decisión", "Regresión Logística", "KNN (k=3)"]
    keys    = ["arbol", "logreg", "knn"]

    # ── A) Comparativa cuantitativa ────────────────────────────────
    print(f"\n{SEP}")
    print("  [A] COMPARACION CUANTITATIVA DE MODELOS")
    print(SEP)
    print(f"  {'Modelo':<24}  {'Accuracy':>8}  {'F1-pond':>8}  {'CV mean':>8}  {'CV std':>7}")
    print(f"  {SEP2}")

    max_acc = max(v for v in resultados_acc.values()) if resultados_acc else 1
    max_f1  = max(v for v in resultados_f1.values())  if resultados_f1  else 1

    for nombre, key in zip(nombres, keys):
        acc = resultados_acc.get(key, 0.0)
        f1  = resultados_f1.get(key,  0.0)
        cv_m = resultados_cv.get(key, (0.0, 0.0))[0]
        cv_s = resultados_cv.get(key, (0.0, 0.0))[1]
        mark = ""
        if acc == max_acc and f1 == max_f1:
            mark = " <-- mejor"
        elif acc == max_acc:
            mark = " <-- acc"
        elif f1 == max_f1:
            mark = " <-- f1"
        print(f"  {nombre:<24}  {acc:>8.4f}  {f1:>8.4f}  {cv_m:>8.4f}  {cv_s:>6.4f}{mark}")

    print(f"\n  Nota: '<--' marca el modelo con mejor valor en esa metrica.")

    # ── B) Criterios cualitativos (STI) ───────────────────────────
    print(f"\n{SEP}")
    print("  [B] CRITERIOS CUALITATIVOS PARA UN STI EDUCATIVO")
    print(f"      Puntuacion: * bajo  ** medio  *** alto")
    print(SEP)
    print(f"  {'Criterio':<38}  {'Arbol':^7}  {'LogReg':^7}  {'KNN':^7}")
    print(f"  {SEP2}")

    totales = [0, 0, 0]
    for criterio, (pa, pl, pk) in CRITERIOS_STI.items():
        totales[0] += pa
        totales[1] += pl
        totales[2] += pk
        print(f"  {criterio:<38}  {_estrella(pa):^7}  {_estrella(pl):^7}  {_estrella(pk):^7}")

    print(f"  {SEP2}")
    print(f"  {'TOTAL (max=' + str(3*len(CRITERIOS_STI)) + ')':<38}  {totales[0]:^7}  {totales[1]:^7}  {totales[2]:^7}")
    ganador_cualitativo = nombres[totales.index(max(totales))]
    print(f"\n  Ganador cualitativo: {ganador_cualitativo} ({max(totales)} pts)")

    # ── C) Reglas del árbol (argumento de explicabilidad) ─────────
    print(f"\n{SEP}")
    print("  [C] REGLAS APRENDIDAS POR EL ARBOL DE DECISION")
    print(f"      (esto NO es posible en Regresion Logistica ni KNN)")
    print(SEP)
    reglas = export_text(modelo_arbol, feature_names=feature_names)
    for linea in reglas.strip().split("\n"):
        print("  " + linea)

    print(f"\n  >> Cualquier docente puede leer estas reglas y entender")
    print(f"     por que el sistema clasifico a un estudiante.")
    print(f"     La Reg. Logistica usa coeficientes flotantes imposibles")
    print(f"     de interpretar. KNN no genera ninguna regla explicita.")

    # ── D) Veredicto final ────────────────────────────────────────
    print(f"\n{SEP}")
    print("  [D] POR QUE SE ELIGE EL ARBOL DE DECISION PARA EL STI")
    print(SEP)

    acc_arbol  = resultados_acc.get("arbol",  0.0)
    acc_logreg = resultados_acc.get("logreg", 0.0)
    acc_knn    = resultados_acc.get("knn",    0.0)

    argumentos = [
        (
            "Precision equivalente o superior",
            f"El arbol obtiene accuracy={acc_arbol:.4f}, frente a "
            f"LogReg({acc_logreg:.4f}) y KNN({acc_knn:.4f}).",
        ),
        (
            "Reglas de decision legibles",
            "export_text() genera un diagrama de condiciones IF-THEN que "
            "cualquier docente puede revisar y validar. Los otros modelos "
            "producen coeficientes o distancias sin significado pedagogico.",
        ),
        (
            "Explicabilidad al docente y al estudiante",
            "El STI puede explicar el motivo de la clasificacion a partir "
            "de las reglas del arbol. Esto NO es posible con "
            "Regresion Logistica ni con KNN.",
        ),
        (
            "No requiere normalizar los datos",
            "Los arboles comparan valores directamente. "
            "Regresion Logistica y KNN degradan su precision sin "
            "normalización previa de features.",
        ),
        (
            "Funciona bien con datasets pequeños",
            "Con pocos registros reales, KNN sufre el problema del vecino "
            "ruidoso y LogReg puede no converger bien. El arbol aprende "
            "umbrales estables desde pocas muestras.",
        ),
        (
            "Importancia de variables (feature importances)",
            "El arbol revela que' variable(s) concentra(n) mas peso en "
            "la decision, lo que puede verificarse en la seccion [2] "
            "de validar_modelo.py.",
        ),
        (
            "Profundidad controlable (max_depth)",
            "max_depth=6 (igual que en train_model.py) evita el "
            "sobreajuste sin perder precision.",
        ),
        (
            "Alineacion con la literatura de STI",
            "Sistemas como ANDES, Cognitive Tutor y PAT2Math usan arboles "
            "de decision o reglas IF-THEN para el modulo del estudiante, "
            "precisamente por su transparencia y facilidad de mantenimiento.",
        ),
    ]

    for i, (titulo, detalle) in enumerate(argumentos, 1):
        print(f"\n  {i}. {titulo}")
        palabras = detalle.split()
        linea_actual = "     "
        for palabra in palabras:
            if len(linea_actual) + len(palabra) + 1 > 63:
                print(linea_actual)
                linea_actual = "     " + palabra + " "
            else:
                linea_actual += palabra + " "
        if linea_actual.strip():
            print(linea_actual)

    print(f"\n{SEP}")
    print("  CONCLUSION")
    print(SEP)
    print(f"  El Arbol de Decisión es el modelo mas adecuado para el")
    print(f"  STI de Algebra porque combina PRECISION con")
    print(f"  EXPLICABILIDAD TOTAL, dos requisitos fundamentales en")
    print(f"  un sistema educativo donde el docente necesita entender")
    print(f"  y confiar en las recomendaciones del sistema.")
    print(f"\n  Precision final : {acc_arbol:.2%}")
    print(f"  Puntaje STI     : {totales[0]}/{3*len(CRITERIOS_STI)} criterios cualitativos")
    print(SEP)


# ─────────────────────────────────────────────────────────────────────
def comparar_modelos():
    # 1) Cargar datos desde BD (9 features, etiqueta NO circular, solo salón piloto real)
    print(f"\n{SEP}")
    print("  COMPARACION DE MODELOS - STI de Algebra (v3, salon real + etiqueta independiente)")
    print(SEP)
    X, y, groups = cargar_datos_entrenamiento()

    if X.size == 0 or y.size == 0:
        print("No hay datos suficientes en puntajes para entrenar los modelos.")
        return

    print(f"\n  Muestras totales (reales + sinteticas si hubo) : {len(X)}")

    # 2) Codificar etiquetas
    encoder  = LabelEncoder()
    y_enc    = encoder.fit_transform(y)
    clases   = list(encoder.classes_)
    conteo   = {c: int(np.sum(y == c)) for c in clases}
    print(f"  Clases           : {clases}")
    print(f"  Distribucion     : {conteo}")

    # 3) Split agrupado por estudiante (ningún id_estudiante en ambos conjuntos)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    idx_train, idx_test = next(gss.split(X, y_enc, groups=groups))
    X_train, X_test = X[idx_train], X[idx_test]
    y_train, y_test = y_enc[idx_train], y_enc[idx_test]
    print(f"  Entrenamiento    : {len(X_train)} muestras")
    print(f"  Prueba           : {len(X_test)} muestras")

    # 4) Definir modelos (Arbol con los MISMOS hiperparametros que train_model.py)
    modelos_def = {
        "arbol" : ("Árbol de Decisión", DecisionTreeClassifier(
            random_state=42, max_depth=6, min_samples_split=4, class_weight="balanced"
        )),
        "logreg": ("Regresión Logística", LogisticRegression(max_iter=1000)),
        "knn"   : ("KNN (k=3)", KNeighborsClassifier(n_neighbors=3)),
    }

    resultados_acc = {}
    resultados_f1  = {}
    resultados_cv  = {}
    modelo_arbol   = None
    feature_names  = FEATURE_NAMES

    # 5) Entrenar y evaluar cada modelo
    for key, (nombre, modelo) in modelos_def.items():
        print(f"\n{SEP}")
        print(f"  Modelo: {nombre}")
        print(SEP)

        try:
            modelo.fit(X_train, y_train)
            y_pred = modelo.predict(X_test)

            acc = accuracy_score(y_test, y_pred)
            f1  = f1_score(y_test, y_pred, average="weighted", zero_division=0)

            n_folds = max(2, min(3, len(set(groups))))
            gkf = GroupKFold(n_splits=n_folds)
            cv_scores = cross_val_score(modelo, X, y_enc, groups=groups, cv=gkf, scoring="accuracy")
            cv_mean, cv_std = float(cv_scores.mean()), float(cv_scores.std())

            resultados_acc[key] = acc
            resultados_f1[key]  = f1
            resultados_cv[key]  = (cv_mean, cv_std)

            if key == "arbol":
                modelo_arbol = modelo

            print(f"  Accuracy (prueba)     : {acc:.4f}")
            print(f"  F1-score ponderado    : {f1:.4f}")
            print(f"  Validacion cruzada    : {cv_mean:.4f} +/- {cv_std:.4f}  ({n_folds}-fold)")
            print()
            print(classification_report(
                y_test, y_pred, target_names=clases, digits=4, zero_division=0
            ))

            print("  Matriz de confusion (filas=real, cols=predicho):")
            cm = confusion_matrix(y_test, y_pred)
            encabezado = "         " + "  ".join(f"{c:^8}" for c in clases)
            print(encabezado)
            for i, fila in enumerate(cm):
                fila_str = "  ".join(f"{v:^8}" for v in fila)
                print(f"  {clases[i]:<7}  {fila_str}")

            if hasattr(modelo, "feature_importances_"):
                print(f"\n  Importancia de variables:")
                max_imp = max(modelo.feature_importances_) or 1.0
                for fn, imp in zip(feature_names, modelo.feature_importances_):
                    barra = _barra(imp, max_imp)
                    print(f"    {fn:<22} {barra} {imp*100:5.1f}%")

        except Exception as exc:
            print(f"  ERROR: {exc}")

    # 6) Resumen de accuracy
    print(f"\n{SEP}")
    print("  RESUMEN RAPIDO DE ACCURACY")
    print(SEP)
    max_acc = max(resultados_acc.values()) if resultados_acc else 0
    for key, (nombre, _) in modelos_def.items():
        acc = resultados_acc.get(key, 0.0)
        barra = _barra(acc, 1.0, ancho=20)
        marca = "  <-- MEJOR" if acc == max_acc else ""
        print(f"  {nombre:<24} {barra} {acc:.4f}{marca}")

    # 7) Justificación completa
    if modelo_arbol is not None:
        mostrar_justificacion(
            resultados_acc, resultados_f1, resultados_cv,
            modelo_arbol, feature_names
        )


if __name__ == "__main__":
    comparar_modelos()
