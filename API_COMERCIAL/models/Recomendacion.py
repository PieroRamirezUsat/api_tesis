from conexionBD import Conexion
import json


class Recomendacion:

    @staticmethod
    def registrar(id_estudiante, id_competencia, recomendacion_texto):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO recomendaciones (id_estudiante, id_competencia, recomendacion, fecha)
                VALUES (%s, %s, %s, NOW())
                RETURNING id_recomendacion;
            """
            cursor.execute(sql, (id_estudiante, id_competencia, recomendacion_texto))
            nuevo_id = cursor.fetchone()["id_recomendacion"]
            con.commit()

            return json.dumps({
                "status": True,
                "message": "Recomendación registrada",
                "id_recomendacion": nuevo_id
            })

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def listar_por_estudiante(id_estudiante):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT 
                    r.id_recomendacion,
                    r.recomendacion,
                    TO_CHAR(r.fecha, 'YYYY-MM-DD HH24:MI') AS fecha,
                    c.descripcion AS competencia
                FROM recomendaciones r
                LEFT JOIN competencias c ON r.id_competencia = c.id_competencia
                WHERE r.id_estudiante = %s
                ORDER BY r.fecha DESC;
            """
            cursor.execute(sql, (id_estudiante,))
            datos = cursor.fetchall()

            return json.dumps({"status": True, "data": datos})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
