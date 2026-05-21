from conexionBD import Conexion
import json


class Material:
    def __init__(
        self,
        id_material=None,
        titulo=None,
        descripcion=None,
        url=None,
        id_competencia=None,
        dificultad=None,
        estado="A",
    ):
        self.id_material = id_material
        self.titulo = titulo
        self.descripcion = descripcion
        self.url = url
        self.id_competencia = id_competencia
        self.dificultad = dificultad  # "basico", "intermedio", "avanzado"
        self.estado = estado          # "A" activo, "I" inactivo

    # ===============================
    # CREAR MATERIAL
    # ===============================
    def crear(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO material_estudio
                    (titulo, descripcion, url, id_competencia, dificultad, estado)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id_material;
            """
            dificultad = self.dificultad if self.dificultad else "basico"
            estado = self.estado if self.estado else "A"

            cursor.execute(
                sql,
                (
                    self.titulo,
                    self.descripcion,
                    self.url,
                    self.id_competencia,
                    dificultad,
                    estado,
                ),
            )
            nuevo_id = cursor.fetchone()["id_material"]
            con.commit()
            return json.dumps(
                {
                    "status": True,
                    "message": "Material registrado correctamente",
                    "id_material": nuevo_id,
                }
            )
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ===============================
    # LISTAR TODO EL MATERIAL
    # ===============================
    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    m.id_material,
                    m.titulo,
                    m.descripcion,
                    m.url,
                    m.id_competencia,
                    m.dificultad,
                    m.estado
                FROM material_estudio m
                ORDER BY m.id_material;
            """
            cursor.execute(sql)
            datos = cursor.fetchall()
            return json.dumps({"status": True, "data": datos})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ===============================
    # OBTENER MATERIAL POR ID
    # ===============================
    @staticmethod
    def obtener(id_material):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    m.id_material,
                    m.titulo,
                    m.descripcion,
                    m.url,
                    m.id_competencia,
                    m.dificultad,
                    m.estado
                FROM material_estudio m
                WHERE m.id_material = %s;
            """
            cursor.execute(sql, (id_material,))
            dato = cursor.fetchone()
            if not dato:
                return json.dumps(
                    {"status": False, "message": "Material no encontrado"}
                )
            return json.dumps({"status": True, "data": dato})
        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ===============================
    # ACTUALIZAR MATERIAL
    # ===============================
    def actualizar(self):
        if not self.id_material:
            return json.dumps(
                {"status": False, "message": "id_material es obligatorio para actualizar"}
            )

        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                UPDATE material_estudio
                SET
                    titulo        = %s,
                    descripcion   = %s,
                    url           = %s,
                    id_competencia= %s,
                    dificultad    = %s,
                    estado        = %s
                WHERE id_material = %s;
            """
            dificultad = self.dificultad if self.dificultad else "basico"
            estado = self.estado if self.estado else "A"

            cursor.execute(
                sql,
                (
                    self.titulo,
                    self.descripcion,
                    self.url,
                    self.id_competencia,
                    dificultad,
                    estado,
                    self.id_material,
                ),
            )
            con.commit()
            return json.dumps(
                {"status": True, "message": "Material actualizado correctamente"}
            )
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()

    # ===============================
    # ELIMINAR MATERIAL
    # ===============================
    @staticmethod
    def eliminar(id_material):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = "DELETE FROM material_estudio WHERE id_material = %s;"
            cursor.execute(sql, (id_material,))
            con.commit()
            return json.dumps(
                {"status": True, "message": "Material eliminado correctamente"}
            )
        except Exception as e:
            con.rollback()
            return json.dumps({"status": False, "message": str(e)})
        finally:
            cursor.close()
            con.close()
