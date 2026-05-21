

from conexionBD import Conexion
import json


class Area:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_area, nombre, descripcion
                FROM area
                ORDER BY id_area;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_area):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_area, nombre, descripcion
                FROM area
                WHERE id_area = %s;
            """, (id_area,))
            dato = cursor.fetchone()

            if not dato:
                return json.dumps({"status": False, "message": "Área no encontrada"})

            return json.dumps({"status": True, "data": dato})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def crear(nombre, descripcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO area (nombre, descripcion)
                VALUES (%s, %s)
                RETURNING id_area;
            """, (nombre, descripcion))
            nuevo_id = cursor.fetchone()["id_area"]
            con.commit()
            return json.dumps({"status": True, "id": nuevo_id, "message": "Área creada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def actualizar(id_area, nombre, descripcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                UPDATE area
                SET nombre = %s, descripcion = %s
                WHERE id_area = %s;
            """, (nombre, descripcion, id_area))
            con.commit()
            return json.dumps({"status": True, "message": "Área actualizada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def eliminar(id_area):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("DELETE FROM area WHERE id_area = %s;", (id_area,))
            con.commit()
            return json.dumps({"status": True, "message": "Área eliminada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
