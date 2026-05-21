from conexionBD import Conexion
import json


class Salon:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_salon, nombre, grado, seccion, estado
                FROM salon
                ORDER BY id_salon;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_salon):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_salon, nombre, grado, seccion, estado
                FROM salon
                WHERE id_salon = %s;
            """, (id_salon,))
            dato = cursor.fetchone()
            if not dato:
                return json.dumps({"status": False, "message": "Salón no encontrado"})
            return json.dumps({"status": True, "data": dato})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def crear(nombre, grado, seccion, estado="A"):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO salon (nombre, grado, seccion, estado)
                VALUES (%s, %s, %s, %s)
                RETURNING id_salon;
            """, (nombre, grado, seccion, estado))
            nuevo_id = cursor.fetchone()["id_salon"]
            con.commit()
            return json.dumps({"status": True, "id": nuevo_id, "message": "Salón creado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def actualizar(id_salon, nombre, grado, seccion, estado="A"):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                UPDATE salon
                SET nombre = %s, grado = %s, seccion = %s, estado = %s
                WHERE id_salon = %s;
            """, (nombre, grado, seccion, estado, id_salon))
            con.commit()
            return json.dumps({"status": True, "message": "Salón actualizado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def eliminar(id_salon):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("DELETE FROM salon WHERE id_salon = %s;", (id_salon,))
            con.commit()
            return json.dumps({"status": True, "message": "Salón eliminado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
