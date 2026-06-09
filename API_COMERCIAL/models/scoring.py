"""
Modelo de puntuación unificado para el STI (Sistema Tutor Inteligente).

Flujo:
  respuesta del alumno → Δ score (por tiempo+resultado) →
  score acumulado (0-100) → nivel (1-7) → progreso % (dona / gráficos)

Score 0-100  Nivel  Progreso  Descripción
  0 - 21       1       0%    Iniciando
 22 - 35       2      20%    Básico
 36 - 49       3      40%    En progreso
 50 - 64       4      60%    Intermedio
 65 - 78       5      80%    Avanzado
 79 - 92       6     100%    Experto  ← meta del alumno
 93 -100       7     100%    Maestro  ← bonus

Umbrales de tiempo por nivel del EJERCICIO (no del alumno):
  El tiempo esperado crece con la dificultad del ejercicio.
  Ejercicio N1 (fácil):    rápido ≤2 min  │ regular 2-6 min  │ lento >6 min
  Ejercicio N2:            rápido ≤2.5min │ regular 2.5-8min │ lento >8 min
  Ejercicio N3 (medio):    rápido ≤3 min  │ regular 3-10 min │ lento >10 min
  Ejercicio N4:            rápido ≤4 min  │ regular 4-12 min │ lento >12 min
  Ejercicio N5+ (difícil): rápido ≤5 min  │ regular 5-15 min │ lento >15 min
"""

# ── Tramos score → nivel ────────────────────────────────────────────────────
SCORE_BRACKETS = [
    (0,  21, 1),
    (22, 35, 2),
    (36, 49, 3),
    (50, 64, 4),
    (65, 78, 5),
    (79, 92, 6),
    (93, 100, 7),
]

# ── Nivel → porcentaje de progreso (dona / barras) ──────────────────────────
NIVEL_PROGRESO = {1: 0, 2: 20, 3: 40, 4: 60, 5: 80, 6: 100, 7: 100}

# ── Nivel → nombre descriptivo ──────────────────────────────────────────────
NIVEL_NOMBRE = {
    1: "Iniciando",
    2: "Básico",
    3: "En progreso",
    4: "Intermedio",
    5: "Avanzado",
    6: "Experto",
    7: "Maestro",
}

# ── Nivel → texto UI del tutor (bajo/medio/alto) ────────────────────────────
# "bajo" → "en construcción" en Android
NIVEL_DISPLAY = {
    1: "bajo",  2: "bajo",
    3: "medio", 4: "medio",
    5: "alto",  6: "alto",  7: "alto",
}

# ── Nivel → filtro SQL de dificultad del ejercicio ──────────────────────────
# 5 bandas distintas para que la racha y el ML tengan efecto real en cada transición
NIVEL_EJERCICIO_WHERE = {
    1: "e.nivel <= 2",              # Iniciando: solo ejercicios N1-N2
    2: "e.nivel <= 3",              # Básico: N1-N3
    3: "e.nivel BETWEEN 2 AND 4",  # En progreso: N2-N4
    4: "e.nivel BETWEEN 3 AND 4",  # Intermedio: N3-N4
    5: "e.nivel >= 4",              # Avanzado: N4+
    6: "e.nivel >= 4",              # Experto: N4+
    7: "e.nivel >= 4",              # Maestro: máximo disponible
}

# ── Umbrales de tiempo por nivel de dificultad del ejercicio ─────────────────
# Tupla: (umbral_rapido_seg, umbral_regular_seg)
#   t <= umbral_rapido              → "rapido"
#   umbral_rapido < t <= umbral_regular → "regular"
#   t > umbral_regular              → "lento"
#
# Razonamiento: cuanto más difícil el ejercicio (algebra no lineal, problemas
# de varios pasos) más tiempo es "normal" para un alumno de secundaria que
# debe resolver en papel, sacar foto y subir su desarrollo.
TIEMPO_THRESHOLDS = {
    1: (120, 360),   # N1 fácil:    rápido ≤2 min   │ regular 2-6 min   │ lento >6 min
    2: (150, 480),   # N2:          rápido ≤2.5 min  │ regular 2.5-8 min │ lento >8 min
    3: (180, 600),   # N3 medio:    rápido ≤3 min    │ regular 3-10 min  │ lento >10 min
    4: (240, 720),   # N4:          rápido ≤4 min    │ regular 4-12 min  │ lento >12 min
    5: (300, 900),   # N5+ difícil: rápido ≤5 min    │ regular 5-15 min  │ lento >15 min
}
# Nivel por defecto (cuando no se conoce el nivel del ejercicio)
_NIVEL_DEFECTO = 3

# ── Tabla de pesos (delta score por respuesta) ───────────────────────────────
# Delta positivo = sube score; negativo = baja score.
# Los mismos deltas sirven para todos los niveles porque el umbral de "rápido"
# ya escala con la dificultad: ser rápido en N5 es más mérito que en N1.
DELTA_SCORE = {
    (True,  "rapido"):  +8,   # dominio total: correcto y rápido para ese nivel
    (True,  "regular"): +5,   # buen manejo: correcto en tiempo normal
    (True,  "lento"):   +2,   # lo logró con esfuerzo
    (False, "rapido"):  -3,   # adivinó o fue impulsivo (incorrecto pero rápido)
    (False, "regular"): -3,   # no conoce bien el tema
    (False, "lento"):   -5,   # no comprende el concepto
}

# ── Estimado de ejercicios para subir de nivel (delta promedio ≈ +3) ─────────
# Nivel 1→2: necesita +22 ≈ 7 ejercicios
# Nivel n→n+1 (n≥2): necesita +14 ≈ 5 ejercicios
EJERCICIOS_POR_NIVEL = {1: 7, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5}


# ── Funciones de conversión ─────────────────────────────────────────────────

def score_to_nivel(score) -> int:
    s = max(0.0, min(100.0, float(score or 0)))
    for lo, hi, nivel in SCORE_BRACKETS:
        if lo <= s <= hi:
            return nivel
    return 7


def nivel_to_progreso(nivel) -> int:
    return NIVEL_PROGRESO.get(int(nivel or 1), 0)


def score_to_progreso(score) -> int:
    return nivel_to_progreso(score_to_nivel(score))


def clasificar_tiempo(segundos, nivel_ejercicio=None) -> str:
    """
    Clasifica el tiempo de respuesta según el nivel de dificultad del ejercicio.

    El alumno resuelve en papel, saca foto y la sube → el tiempo real es largo.
    Los umbrales crecen con la dificultad para no penalizar al alumno que trabaja
    un problema difícil el mismo tiempo que uno fácil.

      nivel_ejercicio  rápido      regular          lento
           1 (fácil)   ≤ 2 min     2 – 6 min       > 6 min
           2           ≤ 2.5 min   2.5 – 8 min     > 8 min
           3 (medio)   ≤ 3 min     3 – 10 min      > 10 min
           4           ≤ 4 min     4 – 12 min      > 12 min
           5+ (difícil)≤ 5 min     5 – 15 min      > 15 min
    """
    if segundos is None:
        return "regular"
    t = float(segundos)

    # Obtener umbrales para el nivel indicado (o el nivel por defecto)
    nivel = int(nivel_ejercicio) if nivel_ejercicio else _NIVEL_DEFECTO
    # Niveles > 5 usan los mismos umbrales que N5
    nivel = max(1, min(nivel, 5))
    umbral_rapido, umbral_regular = TIEMPO_THRESHOLDS[nivel]

    if t <= umbral_rapido:
        return "rapido"
    if t <= umbral_regular:
        return "regular"
    return "lento"


def calcular_delta(es_correcta: bool, tiempo_respuesta, nivel_ejercicio=None) -> int:
    cat = clasificar_tiempo(tiempo_respuesta, nivel_ejercicio)
    return DELTA_SCORE.get((bool(es_correcta), cat), 0)


def nivel_display_texto(nivel_actual: int) -> str:
    return NIVEL_DISPLAY.get(int(nivel_actual or 1), "bajo")
