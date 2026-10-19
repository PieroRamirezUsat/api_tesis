"""
Script de VALIDACIÓN del modelo tutor (STI de Álgebra).

Carga el modelo ya entrenado (modelo_tutor.pkl) y ejecuta
pruebas completas para demostrar su correcto funcionamiento.

Uso:
    python validar_modelo.py

Requiere que train_model.py haya sido ejecutado antes.

Corregido 2026-10-16: antes este script tenía su PROPIA lógica de carga
de datos (5 features, etiqueta circular por umbral de promedio_puntaje),
desalineada con el modelo real de 9 features — hubiera fallado al
llamar modelo.predict() con un vector del tamaño equivocado. Ahora
reutiliza cargar_datos_desde_bd() de train_model.py, la misma fuente
de verdad que usa comparar_modelos_v2.py, para que nunca se desalineen.
"""

import pickle
import sys
import numpy as np
from sklearn.tree import export_text
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, precision_score, recall_score, f1_score
)
from sklearn.model_selection import GroupKFold
from conexionBD import Conexion
from train_model import cargar_datos_desde_bd, RANGO_BAJO_MAX, RANGO_MEDIO_MAX

SEP = "=" * 60


# ─────────────────────────────────────────────────────────────
def _barra(valor, maximo=1.0, ancho=20):
    llenos = int(round(valor / maximo * ancho)) if maximo > 0 else 0
    return "[" + "#" * llenos + "-" * (ancho - llenos) + "]"


def cargar_modelo():
    try:
        with open("modelo_tutor.pkl", "rb") as f:
            datos = pickle.load(f)
        return (
            datos["modelo"],
            datos["encoder"],
            datos["feature_names"],
            datos["umbral_aprobado"],
            datos["umbral_bajo"],
            datos["umbral_medio"],
        )
    except FileNotFoundError:
        print("\n[ERROR] No se encontro modelo_tutor.pkl")
        print("        Ejecuta primero: python train_model.py")
        sys.exit(1)


def cargar_datos():
    """Reutiliza EXACTAMENTE la carga de datos de train_model.py (9 features,
    etiqueta del diagnóstico MINEDU, solo salón piloto real). meta se
    reconstruye a partir de X/groups para las secciones de este script."""
    X, y, groups = cargar_datos_desde_bd()
    meta = [
        {"id_estudiante": int(g), "promedio": float(x[1])}
        for x, g in zip(X, groups)
    ]
    return X, y, groups, meta


# ─────────────────────────────────────────────────────────────
def seccion_1_info_modelo(modelo, encoder, feature_names):
    print(f"\n{SEP}")
    print("  [1] INFORMACION DEL MODELO CARGADO")
    print(SEP)
    print(f"  Algoritmo        : Arbol de Decision (DecisionTreeClassifier)")
    print(f"  Clases conocidas : {list(encoder.classes_)}")
    print(f"  Features         : {feature_names}")
    print(f"  max_depth config : {modelo.max_depth}")
    print(f"  Profundidad real : {modelo.get_depth()}")
    print(f"  Nodos del arbol  : {modelo.tree_.node_count}")
    print(f"  min_samples_split: {modelo.min_samples_split}")
    print(f"  class_weight     : {modelo.class_weight}")


def seccion_2_importancias(modelo, feature_names):
    print(f"\n{SEP}")
    print("  [2] IMPORTANCIA DE CADA VARIABLE (feature importances)")
    print(SEP)
    importancias = modelo.feature_importances_
    maximo = max(importancias) if max(importancias) > 0 else 1.0
    orden  = np.argsort(importancias)[::-1]
    for i in orden:
        barra = _barra(importancias[i], maximo)
        print(f"  {feature_names[i]:<22} {barra}  {importancias[i]*100:5.1f}%")
    print()
    dominante = feature_names[orden[0]]
    print(f"  >> Variable mas influyente: '{dominante}'")
    if importancias[orden[0]] > 0.9:
        print(f"     (domina el 90%+ de las decisiones - logica clara y explicable)")


def seccion_3_reglas(modelo, feature_names):
    print(f"\n{SEP}")
    print("  [3] REGLAS DE DECISION APRENDIDAS POR EL ARBOL")
    print(SEP)
    reglas = export_text(modelo, feature_names=feature_names)
    lineas = reglas.strip().split("\n")
    total  = len(lineas)
    for linea in lineas[:35]:
        print("  " + linea)
    if total > 35:
        print(f"  ... ({total-35} lineas adicionales omitidas)")
    print(f"\n  >> Total de reglas en el arbol: {total} lineas")


def seccion_4_validacion_cruzada(modelo, X, y_encoded, encoder, groups):
    print(f"\n{SEP}")
    print("  [4] VALIDACION CRUZADA AGRUPADA POR ESTUDIANTE")
    print(SEP)
    clases = list(encoder.classes_)
    n      = len(X)

    if n < 10:
        print("  Pocos datos para validacion cruzada (se necesitan >= 10 muestras).")
        return None

    n_folds = max(2, min(5, len(set(groups))))
    skf     = GroupKFold(n_splits=n_folds)

    metricas = {"accuracy": [], "precision": [], "recall": [], "f1": []}
    for fold_i, (train_idx, test_idx) in enumerate(skf.split(X, y_encoded, groups=groups), 1):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y_encoded[train_idx], y_encoded[test_idx]
        modelo.fit(X_tr, y_tr)
        y_pred = modelo.predict(X_te)
        metricas["accuracy"].append(accuracy_score(y_te, y_pred))
        metricas["precision"].append(precision_score(y_te, y_pred, average="weighted", zero_division=0))
        metricas["recall"].append(recall_score(y_te, y_pred, average="weighted", zero_division=0))
        metricas["f1"].append(f1_score(y_te, y_pred, average="weighted", zero_division=0))
        print(f"  Fold {fold_i}/{n_folds}:  acc={metricas['accuracy'][-1]:.3f}  "
              f"prec={metricas['precision'][-1]:.3f}  "
              f"rec={metricas['recall'][-1]:.3f}  "
              f"f1={metricas['f1'][-1]:.3f}")

    print()
    for metrica, valores in metricas.items():
        media = np.mean(valores)
        std   = np.std(valores)
        barra = _barra(media)
        print(f"  {metrica:<12} {barra}  {media:.4f} +/- {std:.4f}")

    acc_media = np.mean(metricas["accuracy"])
    print()
    if acc_media >= 0.90:
        print(f"  >> RESULTADO: EXCELENTE (accuracy media={acc_media:.2%})")
    elif acc_media >= 0.80:
        print(f"  >> RESULTADO: MUY BUENO (accuracy media={acc_media:.2%})")
    elif acc_media >= 0.70:
        print(f"  >> RESULTADO: ACEPTABLE (accuracy media={acc_media:.2%})")
    else:
        print(f"  >> RESULTADO: DEBIL — necesita mas datos reales (accuracy media={acc_media:.2%})")

    # Re-entrenar con todo para dejar el modelo en estado completo
    modelo.fit(X, y_encoded)
    return acc_media


def seccion_5_reporte_completo(modelo, X, y, y_encoded, encoder):
    print(f"\n{SEP}")
    print("  [5] REPORTE SOBRE TODOS LOS DATOS DISPONIBLES")
    print(SEP)
    clases  = list(encoder.classes_)
    y_pred  = modelo.predict(X)

    print(classification_report(
        y_encoded, y_pred,
        target_names=clases,
        zero_division=0
    ))

    cm = confusion_matrix(y_encoded, y_pred)
    print(f"  Matriz de confusion  (filas=real  cols=predicho)")
    print()
    encabezado = "           " + "  ".join(f"{c:^9}" for c in clases)
    print(encabezado)
    for i, fila in enumerate(cm):
        contenido = "  ".join(f"{v:^9}" for v in fila)
        print(f"  {clases[i]:<9}  {contenido}")

    total_correcto = int(np.sum(np.diag(cm)))
    total_total    = int(np.sum(cm))
    print(f"\n  >> Clasificados correctamente: {total_correcto}/{total_total} "
          f"({total_correcto/total_total*100:.1f}%)")


def seccion_6_casos_reales(modelo, encoder, X, y, meta):
    print(f"\n{SEP}")
    print("  [6] CASOS REALES DE ESTUDIANTES EN LA BD")
    print("      (ADVERTENCIA: el modelo fue (re)entrenado con TODO X en la")
    print("       seccion [4]; esta tabla es ajuste en entrenamiento, NO")
    print("       desempeño en datos no vistos — ver [4] para eso)")
    print(SEP)

    print(f"  {'ID Est':>6}  {'Prom':>6}  {'Diagnostico':<11}  {'Predicho':<8}  {'OK?'}")
    print(f"  {'-'*6}  {'-'*6}  {'-'*11}  {'-'*8}  {'-'*4}")

    errores = 0
    for i, (xi, yi) in enumerate(zip(X, y)):
        pred_enc = modelo.predict([xi])[0]
        pred     = encoder.inverse_transform([pred_enc])[0]
        ok       = "OK" if pred == yi else "FALLO"
        if pred != yi:
            errores += 1
        m = meta[i]
        print(f"  {m['id_estudiante']:>6}  "
              f"{m['promedio']:>6.1f}  "
              f"{yi:<11}  "
              f"{pred:<8}  "
              f"{ok}")

    total = len(X)
    print(f"\n  >> Correctos: {total-errores}/{total}   "
          f"Errores: {errores}   "
          f"Precision: {(total-errores)/total*100:.1f}%")


def seccion_7_perfiles_sinteticos(modelo, encoder):
    print(f"\n{SEP}")
    print("  [7] PREDICCION SOBRE PERFILES SINTETICOS DE PRUEBA")
    print("      (sin columna 'esperado': la etiqueta real viene del")
    print("       diagnostico MINEDU, no del patron de interaccion, asi")
    print("       que no hay forma honesta de precalcular que nivel")
    print("       'deberia' salir aqui sin reintroducir circularidad)")
    print(SEP)

    # [total, promedio, min, max, std, tasa, tendencia, tiempo_prom, tasa_pista]
    perfiles = [
        ([2,  15.0, 10.0,  20.0,  5.0, 0.00,  0.0, 300.0, 0.4], "Nuevo, puntajes muy bajos, sin tendencia"),
        ([5,  35.0, 20.0,  45.0, 10.0, 0.10, -0.3, 280.0, 0.5], "Promedio bajo y empeorando"),
        ([8,  55.0, 40.0,  70.0, 15.0, 0.50,  0.0, 180.0, 0.2], "Regular, consistente, estable"),
        ([10, 58.0, 30.0,  90.0, 30.0, 0.50,  0.4, 150.0, 0.2], "Promedio medio pero mejorando y volatil"),
        ([12, 72.0, 60.0,  88.0,  8.0, 0.75,  0.6, 120.0, 0.1], "Buen promedio, consistente, mejorando"),
        ([15, 72.0, 50.0,  95.0, 25.0, 0.60, -0.5, 200.0, 0.3], "Buen promedio PERO empeorando y volatil"),
        ([15, 91.0, 80.0, 100.0,  5.0, 1.00,  0.8,  90.0, 0.0], "Excelente, consistente, mejorando"),
    ]

    print(f"  {'Descripcion':<42}  {'Predicho':<8}  {'Confianza':>9}")
    print(f"  {'-'*42}  {'-'*8}  {'-'*9}")

    for features, desc in perfiles:
        Xp        = np.array([features], dtype=float)
        pred_enc  = modelo.predict(Xp)[0]
        pred      = encoder.inverse_transform([pred_enc])[0]
        proba     = modelo.predict_proba(Xp)[0]
        confianza = max(proba) * 100
        print(f"  {desc:<42}  {pred:<8}  {confianza:>8.1f}%")

    print(f"\n  >> Estos {len(perfiles)} perfiles solo verifican que el modelo")
    print(f"     no se rompe / produce una clase valida con probabilidad para")
    print(f"     cada entrada; no miden precision (ver secciones [4] y [5]).")


def seccion_8_umbrales(umbral_bajo, umbral_medio):
    print(f"\n{SEP}")
    print("  [8] UMBRALES DE CLASIFICACION APLICADOS A LA ETIQUETA")
    print("      (estos umbrales se aplican al puntaje del DIAGNOSTICO")
    print("       MINEDU, no al promedio de interaccion con el sistema —")
    print("       ver Tabla 3 de la tesis / diagnostico_a_nivel() en")
    print("       train_model.py)")
    print(SEP)
    print(f"  Diagnostico < {umbral_bajo}   =>  nivel BAJO")
    print(f"  Diagnostico {umbral_bajo} - {umbral_medio}  =>  nivel MEDIO")
    print(f"  Diagnostico >= {umbral_medio}  =>  nivel ALTO")
    print()
    escala = 50
    print("  Escala de puntajes (0-100):")
    bajo_pos  = int(umbral_bajo  / 100 * escala)
    medio_pos = int(umbral_medio / 100 * escala)
    barra = (
        "[" +
        "B" * bajo_pos +
        "|" +
        "M" * (medio_pos - bajo_pos) +
        "|" +
        "A" * (escala - medio_pos) +
        "]"
    )
    print(f"  0{barra}100")
    print(f"  {'':>{bajo_pos+1}}^{umbral_bajo:<6}{'':>{medio_pos-bajo_pos-1}}^{umbral_medio}")


# ─────────────────────────────────────────────────────────────
def main():
    print(f"\n{SEP}")
    print("  VALIDACION DEL MODELO TUTOR STI - Algebra")
    print("  Sistema Tutor Inteligente - Tesis Universitaria")
    print(SEP)

    # 1. Cargar modelo
    modelo, encoder, feature_names, umb_aprobado, umb_bajo, umb_medio = cargar_modelo()

    seccion_1_info_modelo(modelo, encoder, feature_names)
    seccion_2_importancias(modelo, feature_names)
    seccion_3_reglas(modelo, feature_names)

    # 2. Cargar datos reales
    print(f"\n{SEP}")
    print("  Cargando datos reales desde la BD...")
    print(SEP)
    X, y, groups, meta = cargar_datos()

    conteo = {c: int(np.sum(y == c)) for c in ["bajo", "medio", "alto"]}
    print(f"  Registros encontrados : {len(X)}")
    print(f"  Distribucion por clase: {conteo}")

    acc_cv = None
    if len(X) == 0:
        print("\n  No hay datos en la tabla puntajes para validar.")
        print("  Continuando con validacion sobre perfiles sinteticos...\n")
        seccion_7_perfiles_sinteticos(modelo, encoder)
        seccion_8_umbrales(umb_bajo, umb_medio)
    else:
        y_encoded = encoder.transform(y)
        acc_cv = seccion_4_validacion_cruzada(modelo, X, y_encoded, encoder, groups)
        seccion_5_reporte_completo(modelo, X, y, y_encoded, encoder)
        seccion_6_casos_reales(modelo, encoder, X, y, meta)
        seccion_7_perfiles_sinteticos(modelo, encoder)
        seccion_8_umbrales(umb_bajo, umb_medio)

    print(f"\n{SEP}")
    print("  VALIDACION COMPLETADA")
    print(f"  Modelo: modelo_tutor.pkl")
    print(f"  Algoritmo: DecisionTreeClassifier")
    if acc_cv is None:
        print(f"  Estado: SIN SUFICIENTES DATOS REALES PARA VALIDAR (ver seccion [4])")
    elif acc_cv >= 0.80:
        print(f"  Estado: ACEPTABLE PARA PRODUCCION (CV agrupada={acc_cv:.1%})")
    else:
        print(f"  Estado: NO CUMPLE EL UMBRAL DE PRODUCCION (CV agrupada={acc_cv:.1%} < 80%)")
        print(f"          Ver seccion [4] — se recomienda mas datos reales antes de desplegar.")
    print(SEP + "\n")


if __name__ == "__main__":
    main()
