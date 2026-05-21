from conexionBD import Conexion
import json


class TipoDocumento:

    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_tipo_doc, descripcion
                FROM tipo_documento
                ORDER BY id_tipo_doc;
            """)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def obtener(id_tipo_doc):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                SELECT id_tipo_doc, descripcion
                FROM tipo_documento
                WHERE id_tipo_doc = %s;
            """, (id_tipo_doc,))
            dato = cursor.fetchone()
            if not dato:
                return json.dumps({"status": False, "message": "Tipo documento no encontrado"})
            return json.dumps({"status": True, "data": dato})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def crear(descripcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO tipo_documento (descripcion)
                VALUES (%s)
                RETURNING id_tipo_doc;
            """, (descripcion,))
            nuevo_id = cursor.fetchone()["id_tipo_doc"]
            con.commit()
            return json.dumps({"status": True, "id": nuevo_id, "message": "Tipo documento creado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def actualizar(id_tipo_doc, descripcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("""
                UPDATE tipo_documento
                SET descripcion = %s
                WHERE id_tipo_doc = %s;
            """, (descripcion, id_tipo_doc))
            con.commit()
            return json.dumps({"status": True, "message": "Tipo documento actualizado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    @staticmethod
    def eliminar(id_tipo_doc):
        con = Conexion()
        cursor = con.cursor()
        try:
            cursor.execute("DELETE FROM tipo_documento WHERE id_tipo_doc = %s;", (id_tipo_doc,))
            con.commit()
            return json.dumps({"status": True, "message": "Tipo documento eliminado"})
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
