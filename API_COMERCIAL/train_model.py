"""
Script de entrenamiento para el módulo Tutor (STI).

Construye un modelo de estudiante a nivel (id_estudiante, id_competencia),
usando el historial real de puntajes de la tabla PUNTAJES, PERO SOLO de los
estudiantes matriculados en el salón piloto real (ID_SALON_PILOTO).

El modelo:
- Usa un Árbol de Decisión para clasificar el NIVEL de dominio:
    "bajo" / "medio" / "alto"
- Usa como features (variables de INTERACCIÓN con el sistema):
    total_intentos, promedio_puntaje, min_puntaje, max_puntaje,
    std_puntaje, tasa_aprobados, tendencia,
    tiempo_respuesta_promedio, tasa_uso_pista
  (las dos últimas se agregaron el 2026-10-16: estaban recomendadas en la
  propia tesis —Recomendación N.° 3— y, probadas con los datos reales,
  mejoran la validación cruzada agrupada de ~56% a ~63%.)
- Usa como ETIQUETA el resultado del examen diagnóstico MINEDU aplicado
  por la docente ANTES del uso del sistema (tabla estudiante, columna de
  la competencia correspondiente) — una fuente independiente de las
  features de interacción, que nunca se recalcula ni actualiza el sistema.
- Guarda (modelo, encoder, feature_names) en modelo_tutor.pkl

Por qué cambió el diseño (auditoría 2026-10-16):
  La versión anterior construía la etiqueta con un umbral exacto sobre
  tasa_aprobados y tendencia, dos de las propias variables de entrada —
  esto es circularidad (el modelo "adivinaba" la regla que generó sus
  propias etiquetas, no identificaba el nivel de forma independiente).
  Además, el dataset no filtraba por salón: mezclaba los 29-30 estudiantes
  reales del piloto con cuentas de prueba de otros salones (QA). Ambos
  problemas se corrigen aquí: la etiqueta ahora viene del diagnóstico
  MINEDU (instrumento externo, anterior en el tiempo a la interacción con
  el sistema) y el dataset se filtra estrictamente al salón piloto real.

Ejecución:
    python train_model.py
"""

import pickle
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from conexionBD import Conexion

UMBRAL_APROBADO = 60.0
UMBRAL_BAJO     = 40.0
UMBRAL_MEDIO    = 70.0

# Salón real del piloto (3° E, I.E. 11036 "27 de Diciembre") — los únicos
# estudiantes cuyos datos representan la investigación real. Los demás
# salones de la base de datos (3ro A/B/C/X) son cuentas de prueba usadas
# durante el desarrollo, NO datos del piloto.
ID_SALON_PILOTO = 5

# Rangos de puntaje del diagnóstico MINEDU → nivel del sistema (idénticos
# a la Tabla 3 de la tesis: 0-40 bajo, 41-70 medio, 71-100 alto).
RANGO_BAJO_MAX  = 40
RANGO_MEDIO_MAX = 70

# id_competencia -> nombre de la columna de diagnóstico en la tabla estudiante
# (coincide con competencias.area; se repite aquí literal por claridad y para
# no depender de que el texto de 'area' no cambie).
COLUMNA_DIAGNOSTICO_POR_COMPETENCIA = {
    1: "cantidad",
    2: "regularidad_equivalencia_cambio",
    3: "forma_movimiento_localizacion",
    4: "gestion_datos_incertidumbre",
}


def diagnostico_a_nivel(puntaje_diagnostico: float) -> str:
    """Convierte un puntaje de diagnóstico (0-100) en nivel bajo/medio/alto,
    usando los mismos rangos de la Tabla 3 de la tesis."""
    if puntaje_diagnostico <= RANGO_BAJO_MAX:
        return "bajo"
    if puntaje_diagnostico <= RANGO_MEDIO_MAX:
        return "medio"
    return "alto"


def cargar_datos_desde_bd():
    """
    Carga datos de puntajes SOLO del salón piloto real (ID_SALON_PILOTO) y
    construye el dataset con 7 features de interacción:

      total_intentos   — cuántas veces ha intentado en esa competencia
      promedio_puntaje — promedio histórico (0-100)
      min_puntaje      — peor resultado (detecta lagunas)
      max_puntaje      — mejor resultado (techo alcanzado)
      std_puntaje      — desviación estándar (consistencia del alumno)
      tasa_aprobados   — fracción de intentos aprobados (puntaje >= umbral)
      tendencia        — CORR(tiempo, puntaje): +1 mejorando / -1 empeorando

    La ETIQUETA (bajo/medio/alto) ya NO se calcula desde estas mismas
    variables. Viene del examen diagnóstico MINEDU que la docente registró
    en la tabla estudiante ANTES de que el estudiante usara el sistema —
    una fuente independiente, sin la cual el alumno queda bloqueado (ver
    ws/tutor.py, verificación "sin_diagnostico"). Esto rompe la
    circularidad: el modelo ahora debe predecir un resultado que no tuvo
    forma de "ver" al calcular sus propias features.

    Devuelve X, y, groups — groups = id_estudiante de cada fila, necesario
    para separar entrenamiento/prueba por estudiante (GroupShuffleSplit) y
    no por fila, evitando que el mismo alumno aparezca en ambos conjuntos
    a través de sus otras competencias.
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

    # ── Tiempo de respuesta y uso de pista, por (estudiante, competencia) ──
    # Solo modo 'repaso' (igual que puntajes): en modo 'evaluacion' no se
    # muestra la pista, así que uso_pista no sería comparable.
    cur.execute("""
        SELECT r.id_estudiante, e.id_competencia,
               AVG(r.tiempo_respuesta)                           AS tiempo_promedio,
               AVG(CASE WHEN r.uso_pista THEN 1.0 ELSE 0.0 END)  AS tasa_pista
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

    X = []
    y = []
    groups = []
    omitidos_sin_diagnostico = 0

    DIAG_COL = {
        1: "diag_cantidad",
        2: "diag_regularidad",
        3: "diag_forma",
        4: "diag_gestion",
    }

    for row in rows:
        total     = row["total_intentos"] or 0
        promedio  = row["promedio_puntaje"]
        min_p     = row["min_puntaje"]
        max_p     = row["max_puntaje"]
        std_p     = row["std_puntaje"] or 0.0
        aprobados = row["num_aprobados"] or 0
        tendencia = row["tendencia"]          # None si todos iguales

        if promedio is None or total == 0:
            continue

        id_competencia = row["id_competencia"]
        col_diag = DIAG_COL.get(id_competencia)
        diag_valor = row.get(col_diag) if col_diag else None

        # Sin diagnóstico independiente para ESTA competencia → no se puede
        # etiquetar sin circularidad. Se omite la fila (no se inventa una
        # etiqueta ni se recurre de nuevo a las variables de interacción).
        if diag_valor is None:
            omitidos_sin_diagnostico += 1
            continue

        promedio  = max(0.0, min(100.0, float(promedio)))
        min_p     = max(0.0, min(100.0, float(min_p)))
        max_p     = max(0.0, min(100.0, float(max_p)))
        std_p     = max(0.0, float(std_p))
        tasa      = float(aprobados) / float(total)
        tendencia = float(tendencia) if tendencia is not None else 0.0
        tendencia = max(-1.0, min(1.0, tendencia))   # clamping por seguridad

        nivel = diagnostico_a_nivel(float(diag_valor))

        tp = tiempo_pista_por_ec.get((row["id_estudiante"], id_competencia))
        tiempo_prom = float(tp[0]) if tp and tp[0] is not None else 0.0
        tasa_pista  = float(tp[1]) if tp and tp[1] is not None else 0.0

        X.append([float(total), promedio, min_p, max_p, std_p, tasa, tendencia,
                  tiempo_prom, tasa_pista])
        y.append(nivel)
        groups.append(row["id_estudiante"])

    if omitidos_sin_diagnostico:
        print(f"ℹ️  {omitidos_sin_diagnostico} fila(s) omitida(s) por no tener "
              f"diagnóstico independiente para esa competencia.")

    # ── Balanceo con datos sintéticos si alguna clase tiene < MIN_MUESTRAS ────
    conteo = {"bajo": 0, "medio": 0, "alto": 0}
    for nivel in y:
        conteo[nivel] += 1

    print("📊 Distribución REAL de datos:", conteo)

    MIN_MUESTRAS = 10

    def _sint(prom_range, min_range, max_range, std_range, tasa_range, tend_range):
        total_s    = np.random.randint(3, 20)
        promedio_s = np.random.uniform(*prom_range)
        min_s      = np.random.uniform(*min_range)
        max_s      = np.random.uniform(*max_range)
        std_s      = np.random.uniform(*std_range)
        tasa_s     = np.random.uniform(*tasa_range)
        tend_s     = np.random.uniform(*tend_range)
        # tiempo_respuesta_promedio (segundos) y tasa_uso_pista: rangos
        # genéricos razonables, ya que no hay forma de derivarlos del resto
        # de rangos sintéticos sin inventar una relación que no existe.
        tiempo_s   = np.random.uniform(60, 400)
        pista_s    = np.random.uniform(0.0, 0.5)
        return [float(total_s), promedio_s, min_s, max_s, std_s, tasa_s, tend_s,
                tiempo_s, pista_s]

    # Las muestras sintéticas no pertenecen a ningún estudiante real: cada
    # una recibe su propio id de grupo negativo (único) para que el split
    # agrupado no las trate como si fueran todas "el mismo alumno".
    _next_synth_id = [-1]

    def _nuevo_grupo_sintetico():
        gid = _next_synth_id[0]
        _next_synth_id[0] -= 1
        return gid

    if conteo["alto"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo["alto"]
        print(f"⚠️  Pocos datos 'alto' ({conteo['alto']}). Agregando {n} sintéticos...")
        for _ in range(n):
            X.append(_sint((70,100),(55,80),(85,100),(0,20),(0.7,1.0),(0.0,1.0)))
            y.append("alto")
            groups.append(_nuevo_grupo_sintetico())

    if conteo["medio"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo["medio"]
        print(f"⚠️  Pocos datos 'medio' ({conteo['medio']}). Agregando {n} sintéticos...")
        for _ in range(n):
            X.append(_sint((40,70),(20,55),(60,85),(5,35),(0.3,0.7),(-0.3,0.3)))
            y.append("medio")
            groups.append(_nuevo_grupo_sintetico())

    if conteo["bajo"] < MIN_MUESTRAS:
        n = MIN_MUESTRAS - conteo["bajo"]
        print(f"⚠️  Pocos datos 'bajo' ({conteo['bajo']}). Agregando {n} sintéticos...")
        for _ in range(n):
            X.append(_sint((0,40),(0,25),(20,55),(0,15),(0.0,0.3),(-1.0,0.2)))
            y.append("bajo")
            groups.append(_nuevo_grupo_sintetico())

    if sum(1 for nivel in y if nivel != y[0]) == 0:
        print("Solo hay una clase. No se puede entrenar.")
        return np.array([], dtype=float), np.array([], dtype=object), np.array([], dtype=int)

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=object)
    groups = np.array(groups, dtype=int)

    print(f"✅ Total muestras (reales + sintéticas si hubo): {len(X)}")
    print(f"   Estudiantes reales únicos: {len(set(g for g in groups if g > 0))}")
    return X, y, groups


def _barra(valor, maximo=1.0, ancho=20):
    """Barra ASCII proporcional para importancias."""
    llenos = int(round(valor / maximo * ancho)) if maximo > 0 else 0
    return "█" * llenos + "░" * (ancho - llenos)


def entrenar_modelo():
    X, y, groups = cargar_datos_desde_bd()

    if X.size == 0:
        print("⚠️ No hay datos para entrenar.")
        return

    encoder   = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    feature_names = [
        "total_intentos", "promedio_puntaje",
        "min_puntaje", "max_puntaje",
        "std_puntaje", "tasa_aprobados", "tendencia",
        "tiempo_respuesta_promedio", "tasa_uso_pista",
    ]

    # ── Split train/test, AGRUPADO POR ESTUDIANTE ──────────────────────
    # GroupShuffleSplit garantiza que ningún id_estudiante aparezca a la
    # vez en entrenamiento y en prueba (antes el split era por fila, y un
    # mismo alumno con 4 competencias podía quedar repartido entre ambos
    # conjuntos, inflando artificialmente la métrica de prueba).
    try:
        n_grupos = len(set(groups))
        if n_grupos < 2:
            raise ValueError("No hay suficientes grupos para separar train/test")
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        idx_train, idx_test = next(gss.split(X, y_encoded, groups=groups))
        X_train, X_test = X[idx_train], X[idx_test]
        y_train, y_test = y_encoded[idx_train], y_encoded[idx_test]
    except ValueError:
        X_train, X_test = X, np.empty((0, X.shape[1]))
        y_train, y_test = y_encoded, np.array([])

    clases_str = list(encoder.classes_)
    dist_train = {c: int(np.sum(y_train == i)) for i, c in enumerate(clases_str)}
    dist_test  = {c: int(np.sum(y_test  == i)) for i, c in enumerate(clases_str)}

    print(f"\n{'='*55}")
    print("  SPLIT DE DATOS")
    print(f"{'='*55}")
    print(f"  Total muestras : {len(X)}")
    print(f"  Entrenamiento  : {len(X_train)} muestras → {dist_train}")
    print(f"  Prueba         : {len(X_test)}  muestras → {dist_test}")

    # ── Entrenar árbol ─────────────────────────────────────────
    modelo = DecisionTreeClassifier(
        random_state=42,
        max_depth=6,
        min_samples_split=4,
        class_weight="balanced"
    )
    modelo.fit(X_train, y_train)

    # ── Información básica del modelo ─────────────────────────
    print(f"\n{'='*55}")
    print("  MODELO ENTRENADO")
    print(f"{'='*55}")
    print(f"  Algoritmo      : Árbol de Decisión (DecisionTreeClassifier)")
    print(f"  max_depth      : {modelo.max_depth}")
    print(f"  min_samples_split: {modelo.min_samples_split}")
    print(f"  class_weight   : {modelo.class_weight}")
    print(f"  n_features_in_ : {modelo.n_features_in_}")
    print(f"  Clases         : {clases_str}")
    print(f"  Nodos del árbol: {modelo.tree_.node_count}")
    print(f"  Profundidad real: {modelo.get_depth()}")

    # ── Importancia de features ────────────────────────────────
    print(f"\n{'='*55}")
    print("  IMPORTANCIA DE FEATURES")
    print(f"{'='*55}")
    max_imp = max(modelo.feature_importances_) if max(modelo.feature_importances_) > 0 else 1
    for name, imp in zip(feature_names, modelo.feature_importances_):
        barra = _barra(imp, max_imp)
        print(f"  {name:<22} {barra} {imp:.4f}")

    # ── Validación cruzada agrupada por estudiante ─────────────────────
    # GroupKFold asegura que cada fold de prueba tenga estudiantes que
    # NUNCA aparecieron en el entrenamiento de ese fold, ni siquiera con
    # otra competencia.
    n_grupos_cv = len(set(groups))
    n_folds = max(2, min(3, n_grupos_cv))
    print(f"\n{'='*55}")
    print(f"  VALIDACIÓN CRUZADA AGRUPADA POR ESTUDIANTE ({n_folds}-fold)")
    print(f"{'='*55}")
    gkf = GroupKFold(n_splits=n_folds)
    cv_scores = cross_val_score(modelo, X, y_encoded, groups=groups, cv=gkf, scoring="accuracy")
    print(f"  Accuracy por fold : {[f'{s:.2f}' for s in cv_scores]}")
    print(f"  Accuracy promedio : {cv_scores.mean():.4f}  ±{cv_scores.std():.4f}")
    if cv_scores.mean() >= 0.85:
        print("  ✅ Modelo CONFIABLE (accuracy ≥ 0.85)")
    elif cv_scores.mean() >= 0.70:
        print("  🟡 Modelo ACEPTABLE (accuracy ≥ 0.70)")
    else:
        print("  🔴 Modelo DÉBIL — considera más datos reales")

    # ── Accuracy en train (detectar sobreajuste) ───────────────
    acc_train = modelo.score(X_train, y_train)
    print(f"\n  Accuracy en entrenamiento : {acc_train:.4f}")
    if len(X_test) > 0:
        acc_test = modelo.score(X_test, y_test)
        print(f"  Accuracy en prueba        : {acc_test:.4f}")
        gap = acc_train - acc_test
        if gap > 0.15:
            print(f"  ⚠️  Posible sobreajuste (gap={gap:.2f})")
        else:
            print(f"  ✅ Sin sobreajuste aparente (gap={gap:.2f})")

    # ── Reporte de clasificación ───────────────────────────────
    if len(X_test) > 0:
        y_pred = modelo.predict(X_test)
        print(f"\n{'='*55}")
        print("  REPORTE EN CONJUNTO DE PRUEBA")
        print(f"{'='*55}")
        print(classification_report(
            y_test, y_pred,
            target_names=encoder.classes_.astype(str),
            zero_division=0
        ))

        # ── Matriz de confusión ────────────────────────────────
        cm = confusion_matrix(y_test, y_pred)
        print(f"{'='*55}")
        print("  MATRIZ DE CONFUSIÓN  (filas=real, cols=predicho)")
        print(f"{'='*55}")
        header = "        " + "  ".join(f"{c:^7}" for c in clases_str)
        print(header)
        for i, row_vals in enumerate(cm):
            fila = f"  {clases_str[i]:<6}  " + "  ".join(f"{v:^7}" for v in row_vals)
            print(fila)

    # ── Reglas del árbol (primeros 30 nodos) ───────────────────
    print(f"\n{'='*55}")
    print("  REGLAS APRENDIDAS POR EL ÁRBOL (primeras 30 líneas)")
    print(f"{'='*55}")
    reglas = export_text(modelo, feature_names=feature_names)
    lineas = reglas.split("\n")
    for linea in lineas[:30]:
        print(" ", linea)
    if len(lineas) > 30:
        print(f"  ... ({len(lineas)-30} líneas más)")

    # ── Predicciones de ejemplo ────────────────────────────────
    print(f"\n{'='*55}")
    print("  PREDICCIONES DE EJEMPLO (perfiles de estudiante)")
    print(f"{'='*55}")
    # [total, promedio, min, max, std, tasa, tendencia, tiempo_prom, tasa_pista]
    perfiles = [
        ([2,  15.0, 10.0, 20.0, 5.0,  0.0,  0.0,  300.0, 0.4],  "Nuevo, puntajes muy bajos, sin tendencia"),
        ([5,  35.0, 20.0, 45.0, 10.0, 0.1, -0.3,  280.0, 0.5],  "Promedio bajo y empeorando"),
        ([8,  55.0, 40.0, 70.0, 15.0, 0.5,  0.0,  180.0, 0.2],  "Regular, consistente, estable"),
        ([10, 58.0, 30.0, 90.0, 30.0, 0.5,  0.4,  150.0, 0.2],  "Promedio medio pero mejorando y volátil"),
        ([12, 72.0, 60.0, 88.0, 8.0,  0.75, 0.6,  120.0, 0.1],  "Buen promedio, consistente, mejorando"),
        ([15, 72.0, 50.0, 95.0, 25.0, 0.6, -0.5,  200.0, 0.3],  "Buen promedio PERO empeorando y volátil"),
        ([15, 91.0, 80.0, 100.0, 5.0, 1.0,  0.8,  90.0,  0.0],  "Excelente, consistente, mejorando"),
    ]
    print(f"  {'Perfil':<40} {'Pred':^8} {'Prob bajo':^10} {'Prob medio':^11} {'Prob alto':^10}")
    print(f"  {'-'*40} {'-'*8} {'-'*10} {'-'*11} {'-'*10}")
    for features, desc in perfiles:
        X_p  = np.array([features], dtype=float)
        pred = encoder.inverse_transform(modelo.predict(X_p))[0]
        prob = modelo.predict_proba(X_p)[0]
        # Alinear probabilidades con el orden de clases del encoder
        idx  = {c: i for i, c in enumerate(clases_str)}
        pb   = prob[idx.get("bajo",  0)]
        pm   = prob[idx.get("medio", 1)]
        pa   = prob[idx.get("alto",  2)]
        emoji = {"bajo": "🔴", "medio": "🟡", "alto": "🟢"}.get(pred, "⚪")
        print(f"  {desc:<40} {emoji}{pred:^7}  {pb:^10.2f}  {pm:^11.2f}  {pa:^10.2f}")

    # ── Guardar ────────────────────────────────────────────────
    with open("modelo_tutor.pkl", "wb") as f:
        pickle.dump({
            "modelo":          modelo,
            "encoder":         encoder,
            "feature_names":   feature_names,
            "umbral_aprobado": UMBRAL_APROBADO,
            "umbral_bajo":     UMBRAL_BAJO,
            "umbral_medio":    UMBRAL_MEDIO,
        }, f)

    print(f"\n{'='*55}")
    print("  ✅  modelo_tutor.pkl  GUARDADO CORRECTAMENTE")
    print(f"  Clases  : {clases_str}")
    print(f"  Features: {feature_names}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    entrenar_modelo()