from flask import Blueprint, request, jsonify
from models.HistorialMaterial import HistorialMaterial
from conexionBD import Conexion
import json

ws_historial_material = Blueprint('ws_historial_material', __name__, url_prefix='/historial')

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request
from ws._seguridad import verificar_acceso_estudiante

@ws_historial_material.before_request
def _requiere_token_historial_material():
    verify_jwt_in_request()

# ================================
# REGISTRAR VISUALIZACIÓN
# ================================
@ws_historial_material.route("", methods=["POST"])
def registrar_historial():
    data = request.get_json() or {}

    id_estudiante        = data.get("id_estudiante")
    id_material          = data.get("id_material")
    tiempo_visualizacion = data.get("tiempo_visto") or data.get("tiempo_visualizacion")

    if not id_estudiante or not id_material:
        return jsonify({"status": False, "message": "Faltan parámetros"})

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    # Escribe en historial_material_estudio (tabla activa usada por dominio y progreso)
    con = Conexion()
    cur = con.cursor()
    try:
        # Si el estudiante estuvo >= 240s en el material → completado, si no → visto
        estado_calc = 'completado' if (tiempo_visualizacion or 0) >= 240 else 'visto'

        cur.execute("""
            INSERT INTO historial_material_estudio
                (id_estudiante, id_material, estado,
                 tiempo_visto, veces_revisado, fecha_acceso)
            VALUES (%s, %s, %s, %s, 1, NOW())
            ON CONFLICT (id_estudiante, id_material) DO UPDATE SET
                -- No degradar: si ya estaba completado, se queda completado
                estado         = CASE
                                   WHEN historial_material_estudio.estado = 'completado' THEN 'completado'
                                   ELSE EXCLUDED.estado
                                 END,
                tiempo_visto   = COALESCE(
                                   historial_material_estudio.tiempo_visto, 0)
                                 + COALESCE(EXCLUDED.tiempo_visto, 0),
                veces_revisado = historial_material_estudio.veces_revisado + 1,
                fecha_acceso   = NOW()
        """, (id_estudiante, id_material, estado_calc, tiempo_visualizacion))
        con.commit()
        return jsonify({"status": True, "message": "Historial registrado"})
    except Exception as e:
        con.rollback()
        return jsonify({"status": False, "message": str(e)})
    finally:
        cur.close()
        con.close()


# ================================
# LISTAR HISTORIAL DEL ESTUDIANTE
# ================================
@ws_historial_material.route("/<int:id_estudiante>", methods=["GET"])
def listar_historial(id_estudiante):
    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err
    return jsonify(json.loads(HistorialMaterial.listar(id_estudiante)))

# Actualizar historial
@ws_historial_material.route('/<int:id_historial>', methods=['PUT'])
def actualizar_historial(id_historial):
    data = request.get_json()
    return jsonify(json.loads(HistorialMaterial.actualizar(id_historial, data)))


# ============================================================
# GET /historial/materiales?idEstudiante=<id>
# Historial de materiales vistos por el estudiante
# Tabla: historial_material_estudio JOIN material_estudio
# ============================================================
@ws_historial_material.route('/materiales', methods=['GET'])
def historial_materiales():
    id_estudiante = request.args.get('idEstudiante', type=int)
    if not id_estudiante:
        return jsonify({
            "status": False,
            "mensaje": "idEstudiante es obligatorio"
        }), 400

    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err

    con = Conexion()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT
                hm.id_historial,
                hm.id_material,
                m.titulo,
                m.tipo,
                hm.tiempo_visto,
                hm.veces_revisado,
                hm.fecha_revision,
                hm.fecha_acceso,
                m.tiempo_estimado
            FROM historial_material_estudio hm
            JOIN material_estudio m ON m.id_material = hm.id_material
            WHERE hm.id_estudiante = %s
            ORDER BY COALESCE(hm.fecha_acceso, hm.fecha_revision) DESC
        """, (id_estudiante,))

        rows = cur.fetchall() or []

        def fmt(f):
            if f is None:
                return None
            try:
                return f.strftime("%d/%m/%Y %H:%M")
            except Exception:
                return str(f)

        data = [
            {
                "idHistorial":   r["id_historial"],
                "idMaterial":    r["id_material"],
                "titulo":        r["titulo"],
                "tipo":          r["tipo"],
                "tiempoVisto":    r["tiempo_visto"] or 0,
                "vecesRevisado":  r["veces_revisado"],
                "fechaRevision":  fmt(r["fecha_revision"]),
                "fechaAcceso":    fmt(r["fecha_acceso"]),
                "tiempoEstimado": r["tiempo_estimado"] or 0,
            }
            for r in rows
        ]

        total_tiempo = sum(r["tiempoVisto"] for r in data)
        completados  = sum(
            1 for r in data
            if (r["tiempoVisto"] or 0) >= max((r["tiempoEstimado"] or 1) * 0.5, 1)
        )

        return jsonify({
            "status": True,
            "data": {
                "totalMateriales":       len(data),
                "totalTiempoVisto":      total_tiempo,
                "materialesCompletados": completados,
                "detalle":               data
            }
        }), 200

    except Exception as e:
        print("Error en /historial/materiales:", str(e))
        return jsonify({"status": False, "mensaje": str(e)}), 500
    finally:
        cur.close()
        con.close()
