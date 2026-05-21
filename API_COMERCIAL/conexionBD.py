import os
import psycopg2
import psycopg2.extras
from config import Config


class Conexion:
    def __init__(self):
        """
        Prioriza DATABASE_URL (igual que la app web).
        - En Render: ambos servicios deben tener la MISMA DATABASE_URL.
        - En local: si no hay DATABASE_URL, usa los valores separados
          (host, user, password, dbname, port) de Config.
        """
        db_url = os.getenv("DATABASE_URL")

        if db_url:
            # Modo nube (Render u otro servidor): cadena completa
            self.dblink = psycopg2.connect(db_url)
        else:
            # Modo local: conexión por parámetros separados
            self.dblink = psycopg2.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dbname=Config.DB_NAME,
                port=Config.DB_PORT,
            )

    def cursor(self):
        return self.dblink.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def commit(self):
        self.dblink.commit()

    def rollback(self):
        self.dblink.rollback()

    def close(self):
        self.dblink.close()
