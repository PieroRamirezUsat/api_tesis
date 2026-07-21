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

# ── Nivel interno (1-7) → nivel MINEDU oficial (EBR) ───────────────────────
# Fuente: MINEDU Currículo Nacional 2016, Escala de calificación EBR.
# El STI usa 7 sub-niveles de granularidad fina para el ajuste adaptativo;
# MINEDU define 5 niveles de reporte oficial para comunicar al docente.
#
#  STI interno  │ Score  │ Nivel MINEDU
#  ─────────────┼────────┼─────────────────────
#   1 Iniciando │  0-21  │ Previo al inicio
#   2 Básico    │ 22-35  │ En inicio
#   3 En progr. │ 36-49  │ En proceso
#   4 Intermedio│ 50-64  │ En proceso
#   5 Avanzado  │ 65-78  │ Logrado
#   6 Experto   │ 79-92  │ Logrado
#   7 Maestro   │ 93-100 │ Destacado
NIVEL_MINEDU = {
    1: "Previo al inicio",
    2: "En inicio",
    3: "En proceso",
    4: "En proceso",
    5: "Logrado",
    6: "Logrado",
    7: "Destacado",
}


def nivel_to_minedu(nivel: int) -> str:
    """Retorna el nombre del nivel MINEDU oficial para un nivel interno (1-7)."""
    return NIVEL_MINEDU.get(int(nivel or 1), "Previo al inicio")


# ── Escala LITERAL MINEDU (secundaria) — la que usan los docentes ───────────
# El colegio califica con letras, no números:
#   AD Logro destacado (18-20) · A Logrado (14-17) · B En proceso (11-13) · C En inicio (0-10)
# Mapeo nivel interno 1-7 → letra:  1,2→C · 3,4→B · 5,6→A · 7→AD
LETRA_NOMBRE = {
    "AD": "Logro destacado",
    "A":  "Logrado",
    "B":  "En proceso",
    "C":  "En inicio",
}
LETRA_VIGESIMAL = {"AD": "18-20", "A": "14-17", "B": "11-13", "C": "0-10"}
_LETRA_SCORE_SEMILLA = {"C": 25, "B": 60, "A": 78, "AD": 95}


def nivel_to_letra(nivel_actual: int) -> str:
    """Nivel interno 1-7 → letra MINEDU (AD/A/B/C)."""
    n = int(nivel_actual or 1)
    if n >= 7:
        return "AD"
    if n >= 5:
        return "A"
    if n >= 3:
        return "B"
    return "C"


def letra_nombre(letra: str) -> str:
    return LETRA_NOMBRE.get((letra or "").strip().upper(), "—")


def score_to_letra(score) -> str:
    """Score 0-100 → letra MINEDU (pasando por el nivel 1-7)."""
    return nivel_to_letra(score_to_nivel(score))


def letra_to_score(letra: str):
    """Letra MINEDU → score semilla 0-100 (diagnóstico). None si inválida."""
    return _LETRA_SCORE_SEMILLA.get((letra or "").strip().upper())


# ── Nivel → texto UI del tutor (bajo/medio/alto) ────────────────────────────
# "bajo" → "en construcción" en Android
NIVEL_DISPLAY = {
    1: "bajo",  2: "bajo",
    3: "medio", 4: "medio",
    5: "alto",  6: "alto",  7: "alto",
}

# ── Dificultad real del ejercicio ────────────────────────────────────────────
# La dificultad vive en ejercicios.nivel_logro (escala 1-7, la que escribe el
# CRUD web del docente y el seed). La columna legacy `nivel` quedó abandonada
# (todas las filas = 1), por eso se usa COALESCE: si un ejercicio antiguo no
# tiene nivel_logro, cae a `nivel` y finalmente a 1.
DIFICULTAD_SQL = "COALESCE(e.nivel_logro, e.nivel, 1)"

# ── Nivel del alumno (NEC 1-7) → filtro SQL de dificultad del ejercicio ─────
# Banda deslizante ~[n-1, n+1] sobre nivel_logro para que la racha y el ML
# tengan efecto real en cada transición. NEC 1-2 comparten banda (≤3) porque
# el banco actual no tiene ejercicios con nivel_logro < 2 en todas las
# competencias; ampliar cuando crezca el banco.
NIVEL_EJERCICIO_WHERE = {
    1: f"{DIFICULTAD_SQL} <= 3",             # Iniciando: lo más fácil disponible
    2: f"{DIFICULTAD_SQL} <= 3",             # Básico
    3: f"{DIFICULTAD_SQL} BETWEEN 2 AND 4",  # En progreso
    4: f"{DIFICULTAD_SQL} BETWEEN 3 AND 5",  # Intermedio
    5: f"{DIFICULTAD_SQL} BETWEEN 4 AND 6",  # Avanzado
    6: f"{DIFICULTAD_SQL} >= 5",             # Experto
    7: f"{DIFICULTAD_SQL} >= 6",             # Maestro: máximo disponible
}

# ── Dificultad (1-7) → banda de reporte (1-4) ───────────────────────────────
# Los reportes "Tiempo por Dificultad" (Android + Web) usan 4 bandas con
# nombres y colores fijos: 1=Fácil, 2=Básico, 3=Intermedio, 4=Avanzado.
# Coincide con la semántica del seed (logro 3=Básico, 4-5=Intermedio, 6=Avanzado).
BANDA_DIFICULTAD_SQL = (
    f"CASE WHEN {DIFICULTAD_SQL} <= 2 THEN 1 "
    f"WHEN {DIFICULTAD_SQL} = 3 THEN 2 "
    f"WHEN {DIFICULTAD_SQL} <= 5 THEN 3 "
    f"ELSE 4 END"
)

# ── Umbrales de tiempo por nivel de dificultad del ejercicio ─────────────────
# Recibe la dificultad real (nivel_logro 1-7); los niveles 6-7 usan los
# umbrales de N5 (clasificar_tiempo clampa a 1..5).
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

# Penalización por usar la pista: acertar CON ayuda demuestra menos dominio
# que acertar solo, así el alumno avanza más lento y permanece en la dificultad
# actual hasta que pueda resolver sin apoyo. Solo recorta deltas positivos
# (un fallo con pista ya tiene su delta negativo normal).
PENALIZACION_PISTA = 3   # puntos que se restan al delta positivo
DELTA_MIN_CON_PISTA = 1  # aun con pista, acertar nunca resta puntos

# ── Estimado de ejercicios para subir de nivel (delta promedio ≈ +3) ─────────
# Nivel 1→2: necesita +22 ≈ 7 ejercicios
# Nivel n→n+1 (n≥2): necesita +14 ≈ 5 ejercicios
EJERCICIOS_POR_NIVEL = {1: 7, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5}


# ── Funciones de conversión ─────────────────────────────────────────────────

def score_to_nivel(score) -> int:
    s = max(0.0, min(100.0, float(score or 0)))
    # SCORE_BRACKETS son tramos ENTEROS (0-21, 22-35...) pero el score real
    # puede ser fraccionario (AVG(puntaje) sobre intentos 0/100, ej. 13 de 60
    # correctos = 21.66...). "lo <= s <= hi" dejaba un hueco de 1 punto entre
    # tramos (21 y 22, 35 y 36...) donde NINGUN tramo calzaba y la funcion
    # caia al `return 7` de emergencia -- un alumno con score 21.9 (recien
    # empezando) se clasificaba como nivel 7 "Maestro", el mas dificil.
    # Los tramos estan ordenados ascendente y son contiguos (hi+1 == siguiente
    # lo), asi que basta con el primer tramo cuyo techo no se supere.
    for lo, hi, nivel in SCORE_BRACKETS:
        if s <= hi:
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


def calcular_delta(es_correcta: bool, tiempo_respuesta, nivel_ejercicio=None,
                   uso_pista: bool = False) -> int:
    """
    Delta de score por respuesta. Si el alumno usó la pista y acertó,
    el avance se reduce (PENALIZACION_PISTA) con un piso de +1:
      correcto rápido  +8 → +5 con pista
      correcto regular +5 → +2 con pista
      correcto lento   +2 → +1 con pista
    """
    cat   = clasificar_tiempo(tiempo_respuesta, nivel_ejercicio)
    delta = DELTA_SCORE.get((bool(es_correcta), cat), 0)
    if uso_pista and delta > 0:
        delta = max(DELTA_MIN_CON_PISTA, delta - PENALIZACION_PISTA)
    return delta


def nivel_display_texto(nivel_actual: int) -> str:
    return NIVEL_DISPLAY.get(int(nivel_actual or 1), "bajo")
