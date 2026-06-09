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

# ── Tabla de pesos (delta score por respuesta) ───────────────────────────────
# Tiempo real de un ejercicio de álgebra secundaria (incluye resolver en papel,
# sacar foto y subirla):
#   'rapido'  ≤ 3 min (180 s) — domina el concepto, resuelve con fluidez
#   'regular' 3-10 min (181-600 s) — tiempo normal para un alumno de secundaria
#   'lento'   > 10 min (>600 s)   — dificultad real, necesita refuerzo
# Delta positivo = sube score; negativo = baja score
DELTA_SCORE = {
    (True,  "rapido"):  +8,   # dominio total: correcto y rápido
    (True,  "regular"): +5,   # buen manejo: correcto a tiempo normal
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


def clasificar_tiempo(segundos) -> str:
    """
    Clasifica el tiempo de respuesta de un ejercicio de álgebra de secundaria.
    El alumno debe resolver en papel, sacar foto y subirla → el tiempo real es largo.
      rápido  : ≤ 180 s  (3 min)  — domina el concepto
      regular : 181-600 s (3-10 min) — tiempo normal
      lento   : > 600 s  (>10 min) — necesita refuerzo
    """
    if segundos is None:
        return "regular"
    t = float(segundos)
    if t <= 180:
        return "rapido"
    if t <= 600:
        return "regular"
    return "lento"


def calcular_delta(es_correcta: bool, tiempo_respuesta) -> int:
    cat = clasificar_tiempo(tiempo_respuesta)
    return DELTA_SCORE.get((bool(es_correcta), cat), 0)


def nivel_display_texto(nivel_actual: int) -> str:
    return NIVEL_DISPLAY.get(int(nivel_actual or 1), "bajo")
