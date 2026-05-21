from conexionBD import Conexion
import json


class Estudiante:
    def __init__(
        self,
        id_estudiante=None,
        id_usuario=None,
        id_salon=None,
        operaciones_basicas=None,
        ecuaciones=None,
        funciones=None,
        geometria=None,
        progreso_general=None,
    ):
        self.id_estudiante = id_estudiante
        self.id_usuario = id_usuario
        self.id_salon = id_salon
        self.operaciones_basicas = operaciones_basicas
        self.ecuaciones = ecuaciones
        self.funciones = funciones
        self.geometria = geometria
        self.progreso_general = progreso_general

    # ======================================================
    #   CREAR ESTUDIANTE
    # ======================================================
    def crear(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                INSERT INTO estudiante
                    (id_usuario, id_salon,
                     operaciones_basicas, ecuaciones,
                     funciones, geometria, progreso_general,
                     fecha_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id_estudiante;
            """
            cursor.execute(
                sql,
                (
                    self.id_usuario,
                    self.id_salon,
                    self.operaciones_basicas,
                    self.ecuaciones,
                    self.funciones,
                    self.geometria,
                    self.progreso_general,
                ),
            )
            nuevo_id = cursor.fetchone()["id_estudiante"]
            con.commit()

            return json.dumps(
                {
                    "status": True,
                    "message": "Estudiante registrado correctamente",
                    "id_estudiante": nuevo_id,
                }
            )

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   LISTAR TODOS
    # ======================================================
    @staticmethod
    def listar_todos():
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    e.id_estudiante,
                    e.id_usuario,
                    e.id_salon,
                    e.operaciones_basicas,
                    e.ecuaciones,
                    e.funciones,
                    e.geometria,
                    e.progreso_general,
                    TO_CHAR(e.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                    u.nombre,
                    u.apellidos
                FROM estudiante e
                JOIN usuarios u ON e.id_usuario = u.id_usuario
                ORDER BY e.id_estudiante;
            """
            cursor.execute(sql)
            datos = cursor.fetchall()

            return json.dumps({"status": True, "data": datos})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   OBTENER POR ID_ESTUDIANTE
    # ======================================================
    @staticmethod
    def obtener_por_id(id_estudiante):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    e.id_estudiante,
                    e.id_usuario,
                    e.id_salon,
                    e.operaciones_basicas,
                    e.ecuaciones,
                    e.funciones,
                    e.geometria,
                    e.progreso_general,
                    TO_CHAR(e.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                    u.nombre,
                    u.apellidos
                FROM estudiante e
                JOIN usuarios u ON e.id_usuario = u.id_usuario
                WHERE e.id_estudiante = %s;
            """
            cursor.execute(sql, (id_estudiante,))
            dato = cursor.fetchone()

            if not dato:
                return json.dumps(
                    {"status": False, "message": "Estudiante no encontrado"}
                )

            return json.dumps({"status": True, "data": dato})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   OBTENER POR ID_USUARIO  (para Android)
    # ======================================================
    @staticmethod
    def obtener_por_usuario(id_usuario):
        """
        Usado por:
          - estudianteApi.getEstudiantePorUsuario(idUsuario)
          - InicioFragment / ProgresoFragment (Android)
        """
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    e.id_estudiante,
                    e.id_usuario,
                    e.id_salon,
                    e.operaciones_basicas,
                    e.ecuaciones,
                    e.funciones,
                    e.geometria,
                    e.progreso_general,
                    TO_CHAR(e.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                    u.nombre,
                    u.apellidos
                FROM estudiante e
                JOIN usuarios u ON e.id_usuario = u.id_usuario
                WHERE e.id_usuario = %s
                LIMIT 1;
            """
            cursor.execute(sql, (id_usuario,))
            dato = cursor.fetchone()

            if not dato:
                return json.dumps(
                    {"status": False, "message": "Estudiante no encontrado para ese usuario"}
                )

            # Importante: nombres que Android espera
            dto = {
                "idEstudiante": dato["id_estudiante"],
                "idUsuario": dato["id_usuario"],
                "idSalon": dato["id_salon"],
                "operacionesBasicas": dato["operaciones_basicas"],
                "ecuaciones": dato["ecuaciones"],
                "funciones": dato["funciones"],
                "geometria": dato["geometria"],
                "progresoGeneral": dato["progreso_general"],
                "nombre": dato["nombre"],
                "apellidos": dato["apellidos"],
            }

            return json.dumps({"status": True, "data": dto})

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   ACTUALIZAR (datos básicos + progreso si quieres)
    # ======================================================
    def actualizar(self):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                UPDATE estudiante
                SET id_salon = %s,
                    operaciones_basicas = %s,
                    ecuaciones = %s,
                    funciones = %s,
                    geometria = %s,
                    progreso_general = %s
                WHERE id_estudiante = %s;
            """
            cursor.execute(
                sql,
                (
                    self.id_salon,
                    self.operaciones_basicas,
                    self.ecuaciones,
                    self.funciones,
                    self.geometria,
                    self.progreso_general,
                    self.id_estudiante,
                ),
            )
            con.commit()

            return json.dumps(
                {"status": True, "message": "Estudiante actualizado correctamente"}
            )

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()

    # ======================================================
    #   ELIMINAR
    # ======================================================
    @staticmethod
    def eliminar(id_estudiante):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = "DELETE FROM estudiante WHERE id_estudiante = %s;"
            cursor.execute(sql, (id_estudiante,))
            con.commit()

            return json.dumps(
                {"status": True, "message": "Estudiante eliminado correctamente"}
            )

        except Exception as e:
            return json.dumps({"status": False, "message": str(e)})

        finally:
            cursor.close()
            con.close()
