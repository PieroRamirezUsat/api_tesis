from conexionBD import Conexion
import json


class Respuesta:
    def __init__(self, id_respuesta=None, respuesta_texto=None,
                 id_estudiante=None, id_ejercicio=None, id_opcion=None):
        self.id_respuesta = id_respuesta
        self.respuesta_texto = respuesta_texto
        self.id_estudiante = id_estudiante
        self.id_ejercicio = id_ejercicio
        self.id_opcion = id_opcion

    # ==========================
    #  Crear respuesta
    # ==========================
    def crear(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO respuestas_estudiantes
                    (respuesta_texto, id_estudiante, id_ejercicio, id_opcion, fecha)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING id_respuesta;
            """
            cursor.execute(
                sql,
                (
                    self.respuesta_texto,
                    self.id_estudiante,
                    self.id_ejercicio,
                    self.id_opcion,
                ),
            )
            nuevo_id = cursor.fetchone()["id_respuesta"]
            con.commit()
            return json.dumps(
                {
                    "status": True,
                    "id_respuesta": nuevo_id,
                    "message": "Respuesta registrada",
                }
            )
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ==========================
    #  Listar respuestas
    # ==========================
    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    r.id_respuesta,
                    r.respuesta_texto,
                    TO_CHAR(r.fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha,
                    e.id_estudiante,
                    u.nombre AS estudiante,
                    ej.descripcion AS ejercicio,
                    op.descripcion AS opcion
                FROM respuestas_estudiantes r
                JOIN estudiante e
                  ON r.id_estudiante = e.id_estudiante
                JOIN usuarios u
                  ON e.id_usuario = u.id_usuario
                JOIN ejercicios ej
                  ON r.id_ejercicio = ej.id_ejercicio
                LEFT JOIN opciones_ejercicio op
                  ON r.id_opcion = op.id_opcion
                ORDER BY r.fecha DESC;
            """
            cursor.execute(sql)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ==========================
    #  Obtener respuesta por ID
    # ==========================
    @staticmethod
    def obtener(id_respuesta):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    r.id_respuesta,
                    r.respuesta_texto,
                    TO_CHAR(r.fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha,
                    e.id_estudiante,
                    u.nombre AS estudiante,
                    ej.descripcion AS ejercicio,
                    op.descripcion AS opcion
                FROM respuestas_estudiantes r
                JOIN estudiante e
                  ON r.id_estudiante = e.id_estudiante
                JOIN usuarios u
                  ON e.id_usuario = u.id_usuario
                JOIN ejercicios ej
                  ON r.id_ejercicio = ej.id_ejercicio
                LEFT JOIN opciones_ejercicio op
                  ON r.id_opcion = op.id_opcion
                WHERE r.id_respuesta = %s;
            """
            cursor.execute(sql, (id_respuesta,))
            datos = cursor.fetchone()
            if datos:
                return json.dumps({"status": True, "data": datos})
            else:
                return json.dumps(
                    {"status": False, "message": "Respuesta no encontrada"}
                )
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ==========================
    #  Eliminar respuesta
    # ==========================
    @staticmethod
    def eliminar(id_respuesta):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = "DELETE FROM respuestas_estudiantes WHERE id_respuesta = %s;"
            cursor.execute(sql, (id_respuesta,))
            con.commit()
            return json.dumps({"status": True, "message": "Respuesta eliminada"})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
