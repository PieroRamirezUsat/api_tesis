-- ============================================================
-- FICHAS MATEMÁTICA 3 — Limpieza + palabras_clave + materiales
-- STI de Álgebra — Tesis universitaria
-- Fecha: 2026-05-28
-- Ejecutar en: bd_ejemplo (PostgreSQL, puerto 5432)
-- NIVELES DE MATERIAL → nivel_logro 1-3 = Básico (1)
--                        nivel_logro 4-5 = Intermedio (2)
--                        nivel_logro 6-7 = Avanzado (3)
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- FASE 1: ELIMINAR materiales de prueba (todos genéricos)
-- ────────────────────────────────────────────────────────────
DELETE FROM material_estudio WHERE id_ejercicio IS NULL;

-- ────────────────────────────────────────────────────────────
-- FASE 2: PALABRAS CLAVE + NIVEL LOGRO para ejercicios 106-125
-- ────────────────────────────────────────────────────────────

-- ── Competencia 1 — Interés Simple (ejr 106–110) ──────────
UPDATE ejercicios SET palabras_clave = 'interés simple bono porcentaje capital',
                      nivel_logro = 3                               -- Básico: aplicación directa
WHERE id_ejercicio = 106;

UPDATE ejercicios SET palabras_clave = 'interés simple préstamo ganancia capital tasa',
                      nivel_logro = 3                               -- Básico: aplicación directa
WHERE id_ejercicio = 107;

UPDATE ejercicios SET palabras_clave = 'interés simple límites tolerancia porcentaje',
                      nivel_logro = 4                               -- Intermedio: multi-paso
WHERE id_ejercicio = 108;

UPDATE ejercicios SET palabras_clave = 'interés simple fórmula despejar tiempo tasa anual',
                      nivel_logro = 5                               -- Intermedio: despejar variable
WHERE id_ejercicio = 109;

UPDATE ejercicios SET palabras_clave = 'interés simple cuotas precio crédito mensual',
                      nivel_logro = 6                               -- Avanzado: cuotas contexto financiero
WHERE id_ejercicio = 110;

-- ── Competencia 2 — Progresión Geométrica (ejr 111–113) e Inecuaciones (ejr 114–115) ──
UPDATE ejercicios SET palabras_clave = 'progresión geométrica razón sucesión término ajedrez',
                      nivel_logro = 3                               -- Básico: identificar razón
WHERE id_ejercicio = 111;

UPDATE ejercicios SET palabras_clave = 'progresión geométrica bacterias crecimiento exponencial',
                      nivel_logro = 5                               -- Intermedio: crecimiento exponencial
WHERE id_ejercicio = 112;

UPDATE ejercicios SET palabras_clave = 'progresión geométrica fórmula término enésimo razón',
                      nivel_logro = 6                               -- Avanzado: fórmula término n-ésimo
WHERE id_ejercicio = 113;

UPDATE ejercicios SET palabras_clave = 'inecuaciones lineal desigualdad solución conjunto',
                      nivel_logro = 3                               -- Básico: resolver inecuación simple
WHERE id_ejercicio = 114;

UPDATE ejercicios SET palabras_clave = 'inecuaciones problema aplicación obreros restricciones',
                      nivel_logro = 5                               -- Intermedio: problema de aplicación
WHERE id_ejercicio = 115;

-- ── Competencia 3 — Transformaciones Geométricas (ejr 116–117), Homotecia (118), Semejanza (119–120) ──
UPDATE ejercicios SET palabras_clave = 'reflexión simetría espejo transformación geométrica',
                      nivel_logro = 2                               -- Básico: identificar reflexión
WHERE id_ejercicio = 116;

UPDATE ejercicios SET palabras_clave = 'transformaciones geométricas traslación rotación reflexión',
                      nivel_logro = 3                               -- Básico: clasificar transformación
WHERE id_ejercicio = 117;

UPDATE ejercicios SET palabras_clave = 'homotecia ampliación reducción escala fotocopiadora',
                      nivel_logro = 4                               -- Intermedio: calcular escala
WHERE id_ejercicio = 118;

UPDATE ejercicios SET palabras_clave = 'semejanza triángulos escala proporción construcción',
                      nivel_logro = 5                               -- Intermedio: aplicar proporciones
WHERE id_ejercicio = 119;

UPDATE ejercicios SET palabras_clave = 'semejanza congruencia triángulos criterios proporcionalidad',
                      nivel_logro = 6                               -- Avanzado: distinguir + demostrar
WHERE id_ejercicio = 120;

-- ── Competencia 4 — Estadística (ejr 121–122) y Probabilidad (ejr 123–125) ──
UPDATE ejercicios SET palabras_clave = 'gráfico circular porcentaje interpretar estadística datos',
                      nivel_logro = 2                               -- Básico: leer gráfico
WHERE id_ejercicio = 121;

UPDATE ejercicios SET palabras_clave = 'medidas dispersión rango varianza desviación estándar',
                      nivel_logro = 5                               -- Intermedio: calcular medidas
WHERE id_ejercicio = 122;

UPDATE ejercicios SET palabras_clave = 'probabilidad espacio muestral eventos frecuencia relativa',
                      nivel_logro = 3                               -- Básico: P(E) directa
WHERE id_ejercicio = 123;

UPDATE ejercicios SET palabras_clave = 'probabilidad condicional evento independiente deporte',
                      nivel_logro = 5                               -- Intermedio: P(A|B) guiado
WHERE id_ejercicio = 124;

UPDATE ejercicios SET palabras_clave = 'probabilidad monedas espacio muestral combinaciones',
                      nivel_logro = 6                               -- Avanzado: eventos compuestos
WHERE id_ejercicio = 125;


-- ────────────────────────────────────────────────────────────
-- FASE 3: MATERIALES vinculados por id_ejercicio
-- 2 materiales por ejercicio: video (YouTube) + link (Khan Academy)
-- nivel = 1 → Básico  (nivel_logro 1-3)
-- nivel = 2 → Intermedio (nivel_logro 4-5)
-- nivel = 3 → Avanzado   (nivel_logro 6-7)
-- ────────────────────────────────────────────────────────────

-- ══ COMPETENCIA 1: INTERÉS SIMPLE ════════════════════════════

-- ejr 106 — Patricia, bono laboral  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Interés Simple: fórmula I=C·r·t y ejercicios', 'video',
 'https://www.youtube.com/results?search_query=interes+simple+formula+ejercicios+resueltos+secundaria',
 1, 106, 1),
('Interés simple – Khan Academy', 'link',
 'https://es.khanacademy.org/math/cc-seventh-grade-math/cc-7th-ratio-proportion/cc-7th-interest/v/introduction-to-interest',
 1, 106, 1);

-- ejr 107 — Sebastián, préstamo  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Calcular ganancia con Interés Simple', 'video',
 'https://www.youtube.com/results?search_query=interes+simple+calcular+ganancia+prestamo+capital',
 1, 107, 1),
('Problemas de interés simple – Khan Academy', 'link',
 'https://es.khanacademy.org/math/cc-seventh-grade-math/cc-7th-ratio-proportion/cc-7th-interest',
 1, 107, 1);

-- ejr 108 — Límites de tolerancia  [nivel_logro=4 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Interés Simple con porcentajes: aplicaciones', 'video',
 'https://www.youtube.com/results?search_query=interes+simple+porcentaje+aplicaciones+limites',
 1, 108, 2),
('Porcentajes e interés simple – Khan Academy', 'link',
 'https://es.khanacademy.org/math/cc-seventh-grade-math/cc-7th-ratio-proportion/cc-7th-interest',
 1, 108, 2);

-- ejr 109 — Inmobiliaria, despejar el tiempo  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Interés Simple: despejar el tiempo (t)', 'video',
 'https://www.youtube.com/results?search_query=interes+simple+despejar+tiempo+ejercicios+resueltos',
 1, 109, 2),
('Despejar variables en interés simple – Khan Academy', 'link',
 'https://es.khanacademy.org/math/cc-seventh-grade-math/cc-7th-ratio-proportion/cc-7th-interest',
 1, 109, 2);

-- ejr 110 — Cámara digital, cuotas  [nivel_logro=6 → AVANZADO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Interés Simple: calcular cuotas mensuales', 'video',
 'https://www.youtube.com/results?search_query=interes+simple+cuotas+mensuales+credito+precio+final',
 1, 110, 3),
('Aplicaciones del interés simple – Khan Academy', 'link',
 'https://es.khanacademy.org/math/cc-seventh-grade-math/cc-7th-ratio-proportion/cc-7th-interest',
 1, 110, 3);

-- ══ COMPETENCIA 2: PROGRESIÓN GEOMÉTRICA E INECUACIONES ══════

-- ejr 111 — Ajedrez, razón  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Progresión Geométrica: razón y primeros términos', 'video',
 'https://www.youtube.com/results?search_query=progresion+geometrica+razon+terminos+ejercicios+secundaria',
 2, 111, 1),
('Introducción a sucesiones geométricas – Khan Academy', 'link',
 'https://es.khanacademy.org/math/algebra/x2f8bb11595b61c86:sequences/x2f8bb11595b61c86:introduction-to-geometric-sequences/v/geometric-sequences-introduction',
 2, 111, 1);

-- ejr 112 — Bacterias, crecimiento exponencial  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Progresión Geométrica: crecimiento exponencial', 'video',
 'https://www.youtube.com/results?search_query=progresion+geometrica+crecimiento+exponencial+bacterias+ejercicios',
 2, 112, 2),
('Crecimiento geométrico exponencial – Khan Academy', 'link',
 'https://es.khanacademy.org/math/algebra/x2f8bb11595b61c86:sequences/x2f8bb11595b61c86:introduction-to-geometric-sequences',
 2, 112, 2);

-- ejr 113 — Término enésimo  [nivel_logro=6 → AVANZADO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Fórmula del n-ésimo término en Progresión Geométrica', 'video',
 'https://www.youtube.com/results?search_query=formula+termino+enesimo+progresion+geometrica+ejercicios',
 2, 113, 3),
('Fórmula explícita de sucesiones geométricas – Khan Academy', 'link',
 'https://es.khanacademy.org/math/algebra/x2f8bb11595b61c86:sequences/x2f8bb11595b61c86:constructing-geometric-sequences',
 2, 113, 3);

-- ejr 114 — Diana, inecuaciones  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Inecuaciones lineales: resolver paso a paso', 'video',
 'https://www.youtube.com/results?search_query=inecuaciones+lineales+resolver+paso+a+paso+secundaria',
 2, 114, 1),
('Inecuaciones lineales – Khan Academy', 'link',
 'https://es.khanacademy.org/math/algebra/x2f8bb11595b61c86:solving-equations-inequalities/x2f8bb11595b61c86:linear-inequalities/v/inequalities',
 2, 114, 1);

-- ejr 115 — Obreros, inecuaciones aplicadas  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Inecuaciones: problemas de aplicación con contexto', 'video',
 'https://www.youtube.com/results?search_query=inecuaciones+problemas+aplicacion+contexto+real+secundaria',
 2, 115, 2),
('Modelar situaciones con inecuaciones – Khan Academy', 'link',
 'https://es.khanacademy.org/math/algebra/x2f8bb11595b61c86:solving-equations-inequalities/x2f8bb11595b61c86:linear-inequalities',
 2, 115, 2);

-- ══ COMPETENCIA 3: TRANSFORMACIONES GEOMÉTRICAS Y SEMEJANZA ══

-- ejr 116 — Espejo plano, reflexión  [nivel_logro=2 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Reflexión geométrica: simetría y espejo plano', 'video',
 'https://www.youtube.com/results?search_query=reflexion+geometrica+simetria+espejo+plano+ejemplos',
 3, 116, 1),
('Reflexiones en geometría – Khan Academy', 'link',
 'https://es.khanacademy.org/math/geometry/hs-geo-transformations/hs-geo-reflections/v/reflecting-segment-over-line',
 3, 116, 1);

-- ejr 117 — Identificar tipo de transformación  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Transformaciones: traslación, rotación y reflexión', 'video',
 'https://www.youtube.com/results?search_query=tipos+transformaciones+geometricas+traslacion+rotacion+reflexion+secundaria',
 3, 117, 1),
('Intro a las transformaciones rígidas – Khan Academy', 'link',
 'https://es.khanacademy.org/math/geometry/hs-geo-transformations/hs-geo-intro-euclid/v/language-and-notation-of-basic-geometry',
 3, 117, 1);

-- ejr 118 — Fotocopiadora, homotecia  [nivel_logro=4 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Homotecia: ampliación y reducción con escala', 'video',
 'https://www.youtube.com/results?search_query=homotecia+ampliacion+reduccion+escala+ejercicios+resueltos',
 3, 118, 2),
('Dilataciones (homotecia) – Khan Academy', 'link',
 'https://es.khanacademy.org/math/geometry/hs-geo-transformations/hs-geo-dilations/v/scaling-down-a-triangle-by-half',
 3, 118, 2);

-- ejr 119 — Puente, semejanza de triángulos  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Semejanza de triángulos: escala y proporciones', 'video',
 'https://www.youtube.com/results?search_query=semejanza+triangulos+escala+proporcion+ejercicios+secundaria',
 3, 119, 2),
('Semejanza de triángulos – Khan Academy', 'link',
 'https://es.khanacademy.org/math/geometry/hs-geo-similarity/hs-geo-triangle-similarity-intro/v/similar-triangles-1',
 3, 119, 2);

-- ejr 120 — Palmeras, semejanza y congruencia  [nivel_logro=6 → AVANZADO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Semejanza y Congruencia: diferencias y criterios', 'video',
 'https://www.youtube.com/results?search_query=semejanza+congruencia+triangulos+diferencias+criterios+secundaria',
 3, 120, 3),
('Criterios de semejanza de triángulos – Khan Academy', 'link',
 'https://es.khanacademy.org/math/geometry/hs-geo-similarity/hs-geo-triangle-similarity-intro',
 3, 120, 3);

-- ══ COMPETENCIA 4: ESTADÍSTICA Y PROBABILIDAD ════════════════

-- ejr 121 — Gráfico circular  [nivel_logro=2 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Cómo interpretar gráficos circulares', 'video',
 'https://www.youtube.com/results?search_query=interpretar+grafico+circular+estadistica+porcentaje+ejercicios',
 4, 121, 1),
('Leer gráficos circulares – Khan Academy', 'link',
 'https://es.khanacademy.org/math/statistics-probability/displaying-describing-data/displays-of-distributions/v/reading-pie-graphs',
 4, 121, 1);

-- ejr 122 — Evaluaciones, medidas de dispersión  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Rango, varianza y desviación estándar: paso a paso', 'video',
 'https://www.youtube.com/results?search_query=medidas+dispersion+rango+varianza+desviacion+estandar+secundaria',
 4, 122, 2),
('Varianza y desviación estándar – Khan Academy', 'link',
 'https://es.khanacademy.org/math/statistics-probability/summarizing-quantitative-data/variance-standard-deviation-population/v/range-variance-and-standard-deviation-as-measures-of-dispersion',
 4, 122, 2);

-- ejr 123 — Debate, probabilidad básica  [nivel_logro=3 → BÁSICO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Probabilidad: espacio muestral y eventos', 'video',
 'https://www.youtube.com/results?search_query=probabilidad+espacio+muestral+eventos+ejercicios+secundaria',
 4, 123, 1),
('Probabilidad básica – Khan Academy', 'link',
 'https://es.khanacademy.org/math/statistics-probability/probability-library/basic-theoretical-probability/v/basic-probability',
 4, 123, 1);

-- ejr 124 — Deporte, probabilidad condicional  [nivel_logro=5 → INTERMEDIO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Probabilidad condicional: eventos dependientes', 'video',
 'https://www.youtube.com/results?search_query=probabilidad+condicional+eventos+dependientes+independientes+ejercicios',
 4, 124, 2),
('Probabilidad condicional – Khan Academy', 'link',
 'https://es.khanacademy.org/math/statistics-probability/probability-library/conditional-probability-independence/v/calculating-conditional-probability',
 4, 124, 2);

-- ejr 125 — Monedas, espacio muestral  [nivel_logro=6 → AVANZADO]
INSERT INTO material_estudio (titulo, tipo, url, id_competencia, id_ejercicio, nivel) VALUES
('Probabilidad con monedas: caras y sellos', 'video',
 'https://www.youtube.com/results?search_query=probabilidad+monedas+caras+sello+espacio+muestral+ejercicios',
 4, 125, 3),
('Probabilidad con monedas – Khan Academy', 'link',
 'https://es.khanacademy.org/math/statistics-probability/probability-library/basic-theoretical-probability/v/basic-probability',
 4, 125, 3);

COMMIT;

-- ────────────────────────────────────────────────────────────
-- VERIFICACIÓN FINAL: distribución de materiales por nivel
-- ────────────────────────────────────────────────────────────
SELECT
  e.id_ejercicio,
  e.id_competencia,
  e.nivel_logro,
  CASE WHEN e.nivel_logro BETWEEN 1 AND 3 THEN 'Básico'
       WHEN e.nivel_logro BETWEEN 4 AND 5 THEN 'Intermedio'
       WHEN e.nivel_logro BETWEEN 6 AND 7 THEN 'Avanzado'
       ELSE 'Sin nivel' END AS categoria,
  CASE WHEN e.palabras_clave IS NOT NULL THEN 'SI' ELSE 'NO' END AS tiene_kw,
  COUNT(m.id_material)  AS materiales,
  MAX(m.nivel)          AS nivel_material
FROM ejercicios e
LEFT JOIN material_estudio m ON m.id_ejercicio = e.id_ejercicio
WHERE e.id_ejercicio BETWEEN 106 AND 125
GROUP BY e.id_ejercicio, e.id_competencia, e.nivel_logro, e.palabras_clave
ORDER BY e.id_competencia, e.id_ejercicio;

-- Resumen por nivel de material
SELECT
  CASE m.nivel WHEN 1 THEN 'Básico (1)'
               WHEN 2 THEN 'Intermedio (2)'
               WHEN 3 THEN 'Avanzado (3)'
               ELSE 'Sin nivel' END AS nivel_material,
  COUNT(*) AS total_materiales
FROM material_estudio m
WHERE m.id_ejercicio BETWEEN 106 AND 125
GROUP BY m.nivel
ORDER BY m.nivel;
