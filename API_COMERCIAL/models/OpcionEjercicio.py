from conexionBD import Conexion
import json

class OpcionEjercicio:

    def __init__(self, id_ejercicio=None, letra=None, texto=None, es_correcta=False):
        self.id_ejercicio = id_ejercicio
        self.letra = letra
        self.texto = texto
        self.es_correcta = es_correcta

    # ======================================================
    #   REGISTRAR OPCIÓN
    # ======================================================
    def registrar(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO opciones_ejercicio (id_ejercicio, letra, texto, es_correcta)
                VALUES (%s, %s, %s, %s)
                RETURNING id_opcion;
            """
            cursor.execute(sql, (
                self.id_ejercicio,
                self.letra.upper(),
                self.texto,
                self.es_correcta
            ))

            new_id = cursor.fetchone()["id_opcion"]
            con.commit()

            return json.dumps({
                "status": True,
                "message": "Opción registrada correctamente",
                "id_opcion": new_id
            })

        except Exception as e:
            return json.dumps({
                "status": False,
                "message": str(e)
            })

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   LISTAR OPCIONES POR EJERCICIO
    # ======================================================
    @staticmethod
    def listar_por_ejercicio(id_ejercicio):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT id_opcion, letra, texto, es_correcta
                FROM opciones_ejercicio
                WHERE id_ejercicio = %s
                ORDER BY letra ASC;
            """
            cursor.execute(sql, (id_ejercicio,))
            data = cursor.fetchall()

            return json.dumps({
                "status": True,
                "data": data
            })

        except Exception as e:
            return json.dumps({
                "status": False,
                "message": str(e)
            })

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   VALIDAR SI UNA OPCIÓN ES CORRECTA
    # ======================================================
    @staticmethod
    def es_correcta(id_opcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT es_correcta
                FROM opciones_ejercicio
                WHERE id_opcion = %s;
            """

            cursor.execute(sql, (id_opcion,))
            row = cursor.fetchone()

            if not row:
                return None  # opción no existe

            return row["es_correcta"]

        except Exception as e:
            return None

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   ELIMINAR OPCIÓN
    # ======================================================
    @staticmethod
    def eliminar(id_opcion):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = "DELETE FROM opciones_ejercicio WHERE id_opcion = %s"
            cursor.execute(sql, (id_opcion,))
            con.commit()

            return json.dumps({
                "status": True,
                "message": "Opción eliminada correctamente"
            })

        except Exception as e:
            return json.dumps({
                "status": False,
                "message": str(e)
            })

        finally:
            cursor.close()
            con.close()
