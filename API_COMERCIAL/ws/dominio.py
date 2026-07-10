from flask import Blueprint, jsonify
from conexionBD import Conexion

ws_dominio = Blueprint("ws_dominio", __name__, url_prefix="/dominio")

# ── Protección global del módulo ─────────────────────────────────────────
# Todos los endpoints exigen un JWT válido (la app siempre lo envía en el
# interceptor de Retrofit). Sin esto, cualquiera sin iniciar sesión podía
# leer datos de los estudiantes (menores de edad). Las rutas públicas
# (login/registro) viven en ws/auth.py y las de imágenes en app.py.
from flask_jwt_extended import verify_jwt_in_request
from ws._seguridad import verificar_acceso_estudiante

@ws_dominio.before_request
def _requiere_token_dominio():
    verify_jwt_in_request()

# ============================
# 1. LISTAR TEMAS POR ESTUDIANTE
#    GET /dominio/temas/<id_estudiante>
# ============================
# ws_dominio.py
@ws_dominio.route("/temas/<int:id_estudiante>", methods=["GET"])
def listar_temas_dominio(id_estudiante):
    err = verificar_acceso_estudiante(id_estudiante)
    if err:
        return err
    try:
        conn = Conexion()
        cur = conn.cursor()

        sql = """
        SELECT
            c.id_competencia AS id_tema,
            c.descripcion    AS nombre_tema,

            -- nivel de la competencia solo para mostrar texto
            CASE c.nivel
                WHEN 1 THEN 'BASICO'
                WHEN 2 THEN 'INTERMEDIO'
                WHEN 3 THEN 'AVANZADO'
                ELSE 'SIN NIVEL'
            END AS nivel_texto,

            -- TOTAL de materiales del tema
            COUNT(DISTINCT m.id_material) AS total_materiales,

            -- MATERIALES vistos (completado o visto) por el estudiante
            COALESCE(
                COUNT(
                    DISTINCT CASE
                        WHEN h.estado IN ('completado', 'visto') THEN h.id_material
                    END
                ),
                0
            ) AS materiales_vistos,

            -- NUEVO: conteo por nivel de material
            COALESCE(SUM(CASE WHEN m.nivel = 1 THEN 1 ELSE 0 END), 0) AS materiales_basico,
            COALESCE(SUM(CASE WHEN m.nivel = 2 THEN 1 ELSE 0 END), 0) AS materiales_intermedio,
            COALESCE(SUM(CASE WHEN m.nivel = 3 THEN 1 ELSE 0 END), 0) AS materiales_avanzado

        FROM competencias c
        LEFT JOIN material_estudio m
            ON m.id_competencia = c.id_competencia
        LEFT JOIN historial_material_estudio h
            ON h.id_material = m.id_material
           AND h.id_estudiante = %s
        GROUP BY 
            c.id_competencia,
            c.descripcion,
            c.nivel
        ORDER BY 
            c.id_competencia ASC;
        """

        cur.execute(sql, (id_estudiante,))
        rows = cur.fetchall()

        data = []
        for r in rows:
            data.append({
                "idTema": r["id_tema"],
                "nombre": r["nombre_tema"],
                "nivel": r["nivel_texto"],

                "totalMateriales": r["total_materiales"],
                "materialesVistos": r["materiales_vistos"],

                # campos nuevos para Android
                "materialesBasico": r["materiales_basico"],
                "materialesIntermedio": r["materiales_intermedio"],
                "materialesAvanzado": r["materiales_avanzado"],
            })

        cur.close()
        conn.close()

        return jsonify({"status": True, "data": data}), 200

    except Exception as e:
        print("ERROR listar_temas_dominio:", e)
        return jsonify({"status": False, "message": str(e)}), 500

# ============================
# 2. DETALLE DE TEMA
#    GET /dominio/tema/<id_tema>
# ============================
@ws_dominio.route("/tema/<int:id_tema>", methods=["GET"])
def tema_detalle(id_tema):
    try:
        conn = Conexion()
        cur = conn.cursor()

        # 1) Info del tema (competencia)
        cur.execute(
            """
            SELECT id_competencia, descripcion, area, nivel
            FROM competencias
            WHERE id_competencia = %s
            """,
            (id_tema,),
        )

        row = cur.fetchone()

        if not row:
            cur.close()
            conn.close()
            return jsonify({"status": False, "message": "Tema no encontrado"}), 404

        id_comp = row["id_competencia"]
        nombre_tema = row["descripcion"]
        area = row["area"]
        nivel_competencia = row["nivel"]   # 1, 2 o 3 (nivel de la competencia)

        # 2) 🔁 MATERIALES ASOCIADOS (TODOS LOS NIVELES)
        cur.execute(
            """
            SELECT 
                id_material, 
                titulo, 
                tipo, 
                url, 
                tiempo_estimado,
                nivel
            FROM material_estudio
            WHERE id_competencia = %s
            ORDER BY nivel NULLS LAST, id_material
            """,
            (id_tema,),
        )

        materiales_rows = cur.fetchall()

        materiales = []
        for m in materiales_rows:
            materiales.append({
                "idMaterial": m["id_material"],
                "titulo": m["titulo"],
                "tipo": (m["tipo"] or "").lower(),   # "video", "pdf", "link", etc.
                "url": m["url"],
                "tiempoEstimado": m["tiempo_estimado"],
                "nivel": m["nivel"],                 # 1,2,3 o NULL
            })

        cur.close()
        conn.close()

        data = {
            "idTema": id_comp,
            "nombre": nombre_tema,
            "descripcionTema": f"Introducción a {nombre_tema}",
            "area": area,
            "nivel": nivel_competencia,  # nivel de la competencia (por si lo necesitas)
            "materiales": materiales,    # 👈 AQUÍ YA VAN LOS 6
        }

        return jsonify({"status": True, "data": data}), 200

    except Exception as e:
        print("ERROR tema_detalle:", e)
        return jsonify({"status": False, "message": str(e)}), 500
