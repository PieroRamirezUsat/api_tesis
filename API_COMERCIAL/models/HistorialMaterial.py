from conexionBD import Conexion
import json


class HistorialMaterial:
    @staticmethod
    def registrar(id_estudiante, id_material, tiempo_visualizacion=None):
        """
        Registra que un estudiante vio un material.
        tiempo_visualizacion puede ser segundos, minutos, etc. (numérico).
        """
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO historial_material
                    (id_estudiante, id_material, tiempo_visualizacion, fecha)
                VALUES (%s, %s, %s, NOW());
            """
            cursor.execute(sql, (id_estudiante, id_material, tiempo_visualizacion))
            con.commit()
            return json.dumps(
                {
                    "status": True,
                    "message": "Historial de material registrado correctamente",
                }
            )
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def listar_por_estudiante(id_estudiante):
        """
        Lista el historial de materiales vistos por un estudiante.
        """
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    h.id_historial,
                    h.id_estudiante,
                    h.id_material,
                    h.tiempo_visualizacion,
                    TO_CHAR(h.fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha,
                    m.titulo,
                    m.descripcion,
                    m.url
                FROM historial_material h
                JOIN material_estudio m
                  ON h.id_material = m.id_material
                WHERE h.id_estudiante = %s
                ORDER BY h.fecha DESC;
            """
            cursor.execute(sql, (id_estudiante,))
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
