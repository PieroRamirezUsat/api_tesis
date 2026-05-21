from conexionBD import Conexion
import json
import datetime


class Puntaje:
    @staticmethod
    def actualizar_puntaje(id_estudiante, id_ejercicio, id_opcion):
        """
        Registra un nuevo puntaje (0 o 100) para el estudiante
        según si la opción elegida es correcta o no.

        🔹 No acumula en un solo registro.
        🔹 Cada respuesta genera una fila en la tabla `puntajes`,
           igual que hace /tutor/responder, para que luego se pueda
           calcular AVG, MIN, MAX, etc.
        """
        con = Conexion()
        cursor = con.cursor()
        try:
            # 1. Verificar si la opción es correcta y obtener la competencia
            sql = """
                SELECT o.es_correcta, e.id_competencia
                FROM opciones_ejercicio o
                JOIN ejercicios e ON o.id_ejercicio = e.id_ejercicio
                WHERE o.id_opcion = %s;
            """
            cursor.execute(sql, (id_opcion,))
            resultado = cursor.fetchone()

            if not resultado:
                return json.dumps(
                    {'status': False, 'message': 'Opción o ejercicio no encontrado'}
                )

            es_correcta = bool(resultado['es_correcta'])
            id_competencia = resultado['id_competencia']

            # 2. Puntaje tipo 0/100 (coherente con ws_tutor.responder)
            puntaje = 100 if es_correcta else 0

            sql = """
                INSERT INTO puntajes (puntaje, fecha_registro, id_competencia, id_estudiante)
                VALUES (%s, %s, %s, %s);
            """
            cursor.execute(
                sql,
                (puntaje, datetime.datetime.now(), id_competencia, id_estudiante)
            )

            con.commit()
            return json.dumps(
                {'status': True, 'message': 'Puntaje registrado correctamente'}
            )

        except Exception as e:
            return json.dumps({'status': False, 'message': str(e)})
        finally:
            cursor.close()
            con.close()

    # 3. Listar todos los puntajes
    @staticmethod
    def listar():
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    p.id_puntaje,
                    p.puntaje,
                    TO_CHAR(p.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                    c.descripcion AS competencia,
                    e.id_estudiante,
                    u.nombre,
                    u.apellidos
                FROM puntajes p
                JOIN competencias c ON p.id_competencia = c.id_competencia
                JOIN estudiante e   ON p.id_estudiante = e.id_estudiante
                JOIN usuarios u     ON e.id_usuario = u.id_usuario
                ORDER BY p.fecha_registro DESC;
            """
            cursor.execute(sql)
            datos = cursor.fetchall()
            return json.dumps({'status': True, 'data': datos})
        except Exception as e:
            return json.dumps({'status': False, 'message': str(e)})
        finally:
            cursor.close()
            con.close()

    # 4. Puntajes por estudiante
    @staticmethod
    def obtener_por_estudiante(id_estudiante):
        con = Conexion()
        cursor = con.cursor()
        try:
            sql = """
                SELECT
                    p.id_puntaje,
                    p.puntaje,
                    TO_CHAR(p.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                    c.descripcion AS competencia
                FROM puntajes p
                JOIN competencias c ON p.id_competencia = c.id_competencia
                WHERE p.id_estudiante = %s
                ORDER BY p.fecha_registro DESC;
            """
            cursor.execute(sql, (id_estudiante,))
            datos = cursor.fetchall()
            return json.dumps({'status': True, 'data': datos})
        except Exception as e:
            return json.dumps({'status': False, 'message': str(e)})
        finally:
            cursor.close()
            con.close()
