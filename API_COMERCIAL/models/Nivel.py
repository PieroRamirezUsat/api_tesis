from conexionBD import Conexion
import json


class Nivel:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_nivel, nombre, descripcion
                FROM nivel
                ORDER BY id_nivel;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_nivel):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_nivel, nombre, descripcion
                FROM nivel
                WHERE id_nivel = %s;
            """, (id_nivel,))
            
            dato = cursor.fetchone()

            if not dato:
                return json.dumps({"status": False, "message": "Nivel no encontrado"})

            return json.dumps({"status": True, "data": dato})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
