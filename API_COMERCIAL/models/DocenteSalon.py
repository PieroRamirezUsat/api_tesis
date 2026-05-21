from conexionBD import Conexion
import json


class DocenteSalon:

    @staticmethod
    def listar_por_docente(id_docente):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT ds.id_docente_salon, s.id_salon, s.nombre, s.grado, s.seccion
                FROM docente_salones ds
                JOIN salon s ON ds.id_salon = s.id_salon
                WHERE ds.id_docente = %s;
            """, (id_docente,))
            
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    @staticmethod
    def asignar(id_docente, id_salon):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO docente_salones (id_docente, id_salon)
                VALUES (%s, %s)
            """, (id_docente, id_salon))
            
            con.commit()
            return json.dumps({"status": True, "message": "Salón asignado correctamente"})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
