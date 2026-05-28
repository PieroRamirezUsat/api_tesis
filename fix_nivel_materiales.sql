-- ============================================================
-- FIX: Actualizar nivel_logro de ejercicios 106-125
--      y corregir nivel de materiales asociados
-- STI de Álgebra — Tesis universitaria
-- Ejecutar si el seed anterior ya fue corrido con nivel=1 en todos
-- ============================================================

BEGIN;

-- ── 1) Corregir nivel_logro de ejercicios ──────────────────
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 106;  -- Básico
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 107;  -- Básico  (comp1: 4B+4I+2A)
UPDATE ejercicios SET nivel_logro = 4 WHERE id_ejercicio = 108;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 109;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 6 WHERE id_ejercicio = 110;  -- Avanzado (comp1: 4B+4I+2A)
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 111;  -- Básico  (comp2: 4B+4I+2A)
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 112;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 6 WHERE id_ejercicio = 113;  -- Avanzado
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 114;  -- Básico
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 115;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 2 WHERE id_ejercicio = 116;  -- Básico
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 117;  -- Básico
UPDATE ejercicios SET nivel_logro = 4 WHERE id_ejercicio = 118;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 119;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 6 WHERE id_ejercicio = 120;  -- Avanzado
UPDATE ejercicios SET nivel_logro = 2 WHERE id_ejercicio = 121;  -- Básico
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 122;  -- Intermedio
UPDATE ejercicios SET nivel_logro = 3 WHERE id_ejercicio = 123;  -- Básico
UPDATE ejercicios SET nivel_logro = 5 WHERE id_ejercicio = 124;  -- Intermedio (comp4: 4B+4I+2A)
UPDATE ejercicios SET nivel_logro = 6 WHERE id_ejercicio = 125;  -- Avanzado

-- ── 2) Corregir nivel de materiales usando el mapeo ────────
--   nivel_logro 1-3 → material nivel 1 (Básico)
--   nivel_logro 4-5 → material nivel 2 (Intermedio)
--   nivel_logro 6-7 → material nivel 3 (Avanzado)
UPDATE material_estudio m
SET nivel = CASE
    WHEN e.nivel_logro BETWEEN 1 AND 3 THEN 1
    WHEN e.nivel_logro BETWEEN 4 AND 5 THEN 2
    WHEN e.nivel_logro BETWEEN 6 AND 7 THEN 3
    ELSE 1
END
FROM ejercicios e
WHERE m.id_ejercicio = e.id_ejercicio
  AND m.id_ejercicio BETWEEN 106 AND 125;

COMMIT;

-- Verificar resultado
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
