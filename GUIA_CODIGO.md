# 📚 Guía de código — API REST (TutorMath)

> Guía de estudio para entender, defender y modificar este proyecto.
> Los archivos clave también tienen un bloque "GUÍA DE ESTUDIO" al inicio.

## Qué es este proyecto

Backend Flask que consume la **app móvil Android**. Expone endpoints REST con
autenticación JWT. Comparte la base de datos Postgres con el proyecto web del
docente (repo `tesis`), pero son dos servidores independientes.

```
App Android ── JWT ──► esta API ──► Postgres (Railway) ◄── Web docente
                          │
                          └──► Cloudinary (imágenes) ◄─────── Web docente
```

## Mapa de carpetas (dentro de API_COMERCIAL/)

| Ruta | Qué contiene | Cuándo tocarlo |
|---|---|---|
| `app.py` | Punto de entrada: registra blueprints, JWT, migración automática | Al agregar un blueprint nuevo |
| `conexionBD.py` | Conexión Postgres (psycopg2, filas como **diccionarios**) | Casi nunca |
| `config.py` | Variables de entorno (BD, JWT_SECRET_KEY) | Al agregar una variable |
| `models/scoring.py` | ⭐ TODAS las reglas del sistema adaptativo: score→nivel, deltas por acierto/fallo, umbrales de tiempo | Para ajustar la pedagogía |
| `ws/tutor.py` | ⭐ El ciclo adaptativo completo (ejercicio_siguiente → responder → pista/material) | El corazón de la tesis |
| `ws/auth.py` | Registro/login de estudiantes, JWT, recuperar contraseña | Cambios de seguridad |
| `ws/progreso.py` | Métricas de progreso (radar, tiempo por dificultad, historial) | Reportes de la app |
| `ws/ejercicio.py` | CRUD/consulta de ejercicios (usado también para rehidratar el ejercicio en la app) | Banco de ejercicios |
| `ws/evaluacion*/docente*/salon*` etc. | Un blueprint por tabla/dominio | Según el dominio |
| `train_model.py` | Entrena el árbol de decisión → `modelo_tutor.pkl` | Re-entrenar el ML |
| `modelo_tutor.pkl` | Modelo entrenado que carga `ws/tutor.py` al arrancar | Se regenera, no se edita |

## El ciclo adaptativo en 60 segundos (para la sustentación)

1. La app pide `GET /tutor/ejercicio_siguiente`. El servidor lee el nivel del
   alumno en esa competencia (tabla `nivel_estudiante_competencia`, "NEC").
2. El **árbol de decisión** (ML) + la racha de aciertos deciden si toca más
   fácil / igual / más difícil, y se elige al azar un ejercicio del banco cuya
   dificultad (`nivel_logro` 1-7) esté en la banda `[nivel−1, nivel+1]`.
3. La app manda `POST /tutor/responder`. El servidor (nunca el cliente) valida
   la respuesta, guarda tiempo y resultado, y aplica el delta de score:
   **+8/+5/+2** si acierta (según rapidez), **−3/−5** si falla; usar pista
   recorta el premio. El score (0-100) se convierte a nivel (1-7) con los
   brackets de `scoring.py`.
4. Si falla: 1er fallo → pista; 2do fallo → material de estudio vinculado a
   ESE ejercicio (`material_estudio.id_ejercicio`) + enlaces de búsqueda.
5. El diagnóstico MINEDU que registra el docente en la web fija el NEC
   inicial; después manda la práctica.

## Tablas de BD que importan

- `usuarios` / `estudiante` / `docente` — cuentas (contraseña = hash werkzeug)
- `nivel_estudiante_competencia` (NEC) — ⭐ nivel y score vivos por competencia
- `ejercicios` + `opciones_ejercicio` — banco (correcta = `es_correcta`)
- `respuestas_estudiantes` — cada intento: tiempo, pista, modo, desarrollo_url
- `material_estudio` — 2 por ejercicio (búsqueda YouTube + enlace directo)
- `evaluaciones` + `evaluacion_*` — modo examen del docente

## Producción (Railway)

- `Procfile` → `gunicorn app:app`. Root Directory del servicio = `API_COMERCIAL`.
- Variables: `DATABASE_URL` (referencia al Postgres), `JWT_SECRET_KEY`,
  `CLOUDINARY_URL`.
- ⚠️ No dejar `railway.toml`/`Procfile` duplicados en la RAÍZ del repo: chocan
  con el Root Directory (ya pasó: error "can't chdir").