from conexionBD import Conexion
import json


class Competencia:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_competencia, descripcion, area, nivel
                FROM competencias
                ORDER BY id_competencia;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_competencia):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_competencia, descripcion, area, nivel
                FROM competencias
                WHERE id_competencia = %s;
            """, (id_competencia,))
            dato = cursor.fetchone()

            if not dato:
                return json.dumps({"status": False, "message": "Competencia no encontrada"})

            return json.dumps({"status": True, "data": dato})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def crear(descripcion, area, nivel):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO competencias (descripcion, area, nivel)
                VALUES (%s, %s, %s)
                RETURNING id_competencia;
            """, (descripcion, area, nivel))
            nuevo_id = cursor.fetchone()["id_competencia"]
            con.commit()
            return json.dumps({"status": True, "id": nuevo_id, "message": "Competencia creada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def actualizar(id_competencia, descripcion, area, nivel):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                UPDATE competencias
                SET descripcion = %s, area = %s, nivel = %s
                WHERE id_competencia = %s;
            """, (descripcion, area, nivel, id_competencia))
            con.commit()
            return json.dumps({"status": True, "message": "Competencia actualizada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def eliminar(id_competencia):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("DELETE FROM competencias WHERE id_competencia = %s;", (id_competencia,))
            con.commit()
            return json.dumps({"status": True, "message": "Competencia eliminada"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
