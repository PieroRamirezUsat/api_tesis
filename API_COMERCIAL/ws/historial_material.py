from flask import Blueprint, request, jsonify
from models.HistorialMaterial import HistorialMaterial
from conexionBD import Conexion
import json

ws_historial_material = Blueprint('ws_historial_material', __name__, url_prefix='/historial')


# ================================
# REGISTRAR VISUALIZACIÓN
# ================================
@ws_historial_material.route("", methods=["POST"])
def registrar_historial():
    data = request.get_json()

    id_estudiante = data.get("id_estudiante")
    id_material = data.get("id_material")
    tiempo_visualizacion = data.get("tiempo_visualizacion")

    return jsonify(json.loads(
        HistorialMaterial.registrar(id_estudiante, id_material, tiempo_visualizacion)
    ))


# ================================
# LISTAR HISTORIAL DEL ESTUDIANTE
# ================================
@ws_historial_material.route("/<int:id_estudiante>", methods=["GET"])
def listar_historial(id_estudiante):
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
