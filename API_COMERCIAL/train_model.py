"""
Script de entrenamiento para el módulo Tutor (STI).

Construye un modelo de estudiante simplificado a nivel
(id_estudiante, id_competencia), usando el historial de puntajes
de la tabla PUNTAJES.

El modelo:
- Usa un Árbol de Decisión para clasificar el NIVEL de dominio:
    "bajo" / "medio" / "alto"
- Usa como features:
    total_intentos, promedio, mínimo, máximo, tasa_aprobados
- Guarda (modelo, encoder, feature_names) en modelo_tutor.pkl

Ejecución:
    python train_model.py
"""

import pickle
import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from conexionBD import Conexion

UMBRAL_APROBADO = 60.0
UMBRAL_BAJO     = 40.0
UMBRAL_MEDIO    = 70.0


def cargar_datos_desde_bd():
    con = Conexion()
    cur = con.cursor()

    cur.execute("""
        SELECT
            p.id_estudiante,
            p.id_competencia,
            COUNT(*)        AS total_intentos,
            AVG(p.puntaje)  AS promedio_puntaje,
            MIN(p.puntaje)  AS min_puntaje,
            MAX(p.puntaje)  AS max_puntaje,
            SUM(CASE WHEN p.puntaje >= %s THEN 1 ELSE 0 END) AS num_aprobados
        FROM puntajes p
        GROUP BY p.id_estudiante, p.id_competencia
        HAVING COUNT(*) >= 1
    """, (UMBRAL_APROBADO,))

    rows = cur.fetchall()
    cur.close()
    con.close()

    X = []
    y = []

    for row in rows:
        total     = row["total_intentos"] or 0
        promedio  = row["promedio_puntaje"]
        min_p     = row["min_puntaje"]
        max_p     = row["max_puntaje"]
        aprobados = row["num_aprobados"] or 0

        if promedio is None or total == 0:
            continue

        promedio = max(0.0, min(100.0, float(promedio)))
        min_p    = max(0.0, min(100.0, float(min_p)))
        max_p    = max(0.0, min(100.0, float(max_p)))
        tasa     = float(aprobados) / float(total)

        if promedio < UMBRAL_BAJO:
            nivel = "bajo"
        elif promedio < UMBRAL_MEDIO:
            nivel = "medio"
        else:
            nivel = "alto"

        X.append([float(total), promedio, min_p, max_p, tasa])
        y.append(nivel)

    # ✅ NUEVO: si hay muy pocas muestras de alguna clase,
    # agregamos datos sintéticos balanceados para que el modelo
    # aprenda todos los niveles
    conteo = {"bajo": 0, "medio": 0, "alto": 0}
    for nivel in y:
        conteo[nivel] += 1

    print("📊 Distribución real de datos:", conteo)

    # Si alguna clase tiene menos de 5 muestras, agregar sintéticos
    MIN_MUESTRAS = 10

    if conteo["alto"] < MIN_MUESTRAS:
        print(f"⚠️ Pocos datos 'alto' ({conteo['alto']}). Agregando sintéticos...")
        for _ in range(MIN_MUESTRAS - conteo["alto"]):
            total_s   = np.random.randint(5, 20)
            promedio_s = np.random.uniform(70, 100)
            min_s      = np.random.uniform(60, 80)
            max_s      = np.random.uniform(85, 100)
            tasa_s     = np.random.uniform(0.7, 1.0)
            X.append([float(total_s), promedio_s, min_s, max_s, tasa_s])
            y.append("alto")

    if conteo["medio"] < MIN_MUESTRAS:
        print(f"⚠️ Pocos datos 'medio' ({conteo['medio']}). Agregando sintéticos...")
        for _ in range(MIN_MUESTRAS - conteo["medio"]):
            total_s   = np.random.randint(3, 15)
            promedio_s = np.random.uniform(40, 70)
            min_s      = np.random.uniform(20, 50)
            max_s      = np.random.uniform(60, 85)
            tasa_s     = np.random.uniform(0.3, 0.7)
            X.append([float(total_s), promedio_s, min_s, max_s, tasa_s])
            y.append("medio")

    if conteo["bajo"] < MIN_MUESTRAS:
        print(f"⚠️ Pocos datos 'bajo' ({conteo['bajo']}). Agregando sintéticos...")
        for _ in range(MIN_MUESTRAS - conteo["bajo"]):
            total_s   = np.random.randint(1, 10)
            promedio_s = np.random.uniform(0, 40)
            min_s      = np.random.uniform(0, 30)
            max_s      = np.random.uniform(20, 50)
            tasa_s     = np.random.uniform(0.0, 0.3)
            X.append([float(total_s), promedio_s, min_s, max_s, tasa_s])
            y.append("bajo")

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=object)

    print(f"✅ Total muestras (reales + sintéticas): {len(X)}")
    return X, y


def _barra(valor, maximo=1.0, ancho=20):
    """Barra ASCII proporcional para importancias."""
    llenos = int(round(valor / maximo * ancho)) if maximo > 0 else 0
    return "█" * llenos + "░" * (ancho - llenos)


def entrenar_modelo():
    X, y = cargar_datos_desde_bd()

    if X.size == 0:
        print("⚠️ No hay datos para entrenar.")
        return

    encoder   = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    feature_names = [
        "total_intentos", "promedio_puntaje",
        "min_puntaje", "max_puntaje", "tasa_aprobados"
    ]

    # ── Split train/test ───────────────────────────────────────
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42,
            stratify=y_encoded if len(set(y_encoded)) > 1 else None
        )
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

    # ── Validación cruzada (3-fold) ────────────────────────────
    print(f"\n{'='*55}")
    print("  VALIDACIÓN CRUZADA (3-fold, sobre TODO el dataset)")
    print(f"{'='*55}")
    cv_scores = cross_val_score(modelo, X, y_encoded, cv=3, scoring="accuracy")
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
    perfiles = [
        ([2,  15.0, 10.0, 20.0, 0.0],  "Estudiante nuevo, puntajes muy bajos"),
        ([5,  35.0, 20.0, 45.0, 0.1],  "Pocos intentos, promedio bajo"),
        ([8,  55.0, 40.0, 70.0, 0.5],  "Regular, mitad aprobados"),
        ([12, 72.0, 60.0, 88.0, 0.75], "Buen promedio, mayoría aprobados"),
        ([15, 91.0, 80.0, 100.0, 1.0], "Excelente, todos aprobados"),
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