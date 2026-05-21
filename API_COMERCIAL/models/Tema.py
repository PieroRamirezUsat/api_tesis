from conexionBD import Conexion
import json


class Tema:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_tema, nombre, descripcion, area
                FROM tema
                ORDER BY id_tema;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_tema):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_tema, nombre, descripcion, area
                FROM tema
                WHERE id_tema = %s;
            """, (id_tema,))
            
            dato = cursor.fetchone()

            if not dato:
                return json.dumps({"status": False, "message": "Tema no encontrado"})

            return json.dumps({"status": True, "data": dato})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def crear(nombre, descripcion, area):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO tema (nombre, descripcion, area)
                VALUES (%s, %s, %s)
                RETURNING id_tema;
            """, (nombre, descripcion, area))
            
            new_id = cursor.fetchone()["id_tema"]
            con.commit()

            return json.dumps({"status": True, "id": new_id, "message": "Tema creado"})

        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def eliminar(id_tema):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("DELETE FROM tema WHERE id_tema = %s;", (id_tema,))
            con.commit()
            return json.dumps({"status": True, "message": "Tema eliminado"})

        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
