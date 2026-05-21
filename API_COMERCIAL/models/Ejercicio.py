from conexionBD import Conexion
import json


class Ejercicio:

    def __init__(self, id_ejercicio=None, id_competencia=None, descripcion=None,
                 imagen_url=None, requiere_desarrollo=False):
        self.id_ejercicio = id_ejercicio
        self.id_competencia = id_competencia
        self.descripcion = descripcion
        self.imagen_url = imagen_url
        self.requiere_desarrollo = requiere_desarrollo

    # ======================================================
    #   REGISTRAR EJERCICIO
    # ======================================================
    def registrar(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO ejercicios
                    (id_competencia, descripcion, imagen_url, requiere_desarrollo, fecha_creacion)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING id_ejercicio;
            """
            cursor.execute(sql, (
                self.id_competencia,
                self.descripcion,
                self.imagen_url,
                self.requiere_desarrollo
            ))

            new_id = cursor.fetchone()["id_ejercicio"]
            con.commit()

            return json.dumps({
                "status": True,
                "message": "Ejercicio registrado correctamente",
                "id_ejercicio": new_id
            })

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   LISTAR EJERCICIOS (opc. por competencia)
    # ======================================================
    @staticmethod
    def listar(id_competencia=None):
        con = Conexion()
        cursor = con.cursor()
        try:
            if id_competencia:
                sql = """
                    SELECT e.id_ejercicio, e.descripcion, e.imagen_url,
                           e.requiere_desarrollo, c.nombre AS competencia
                    FROM ejercicios e
                    JOIN competencias c ON c.id_competencia = e.id_competencia
                    WHERE e.id_competencia = %s
                    ORDER BY e.id_ejercicio ASC;
                """
                cursor.execute(sql, (id_competencia,))
            else:
                sql = """
                    SELECT e.id_ejercicio, e.descripcion, e.imagen_url,
                           e.requiere_desarrollo, c.nombre AS competencia
                    FROM ejercicios e
                    JOIN competencias c ON c.id_competencia = e.id_competencia
                    ORDER BY e.id_ejercicio ASC;
                """
                cursor.execute(sql)

            data = cursor.fetchall()
            return json.dumps({"status": True, "data": data})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   OBTENER DETALLE DE EJERCICIO
    # ======================================================
    @staticmethod
    def obtener(id_ejercicio):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT e.id_ejercicio, e.id_competencia, c.nombre AS competencia,
                       e.descripcion, e.imagen_url, e.requiere_desarrollo
                FROM ejercicios e
                JOIN competencias c ON c.id_competencia = e.id_competencia
                WHERE e.id_ejercicio = %s;
            """
            cursor.execute(sql, (id_ejercicio,))
            row = cursor.fetchone()

            if not row:
                return json.dumps({"status": False, "message": "Ejercicio no encontrado"})

            return json.dumps({"status": True, "data": row})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   ELIMINAR EJERCICIO
    # ======================================================
    @staticmethod
    def eliminar(id_ejercicio):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = "DELETE FROM ejercicios WHERE id_ejercicio = %s"
            cursor.execute(sql, (id_ejercicio,))
            con.commit()

            return json.dumps({
                "status": True,
                "message": "Ejercicio eliminado correctamente"
            })

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
