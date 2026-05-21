from conexionBD import Conexion
import json


class Salon:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_salon, nombre, grado, seccion
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
                SELECT id_salon, nombre, grado, seccion
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
