# ═══════════════════════════════════════════════════════════════════════════
#  📚 GUÍA DE ESTUDIO — CONEXIÓN A LA BASE DE DATOS (API)
# ═══════════════════════════════════════════════════════════════════════════
#  Cada endpoint crea su propia Conexion() y la cierra al terminar (patrón
#  try/finally). OJO: esta API usa psycopg2 con RealDictCursor → las filas
#  se leen como DICCIONARIOS (row["columna"]). El proyecto web usa psycopg
#  v3 con tuplas (row[0]) — no confundir los dos estilos al copiar código
#  entre proyectos.
#
#  Prioridad de configuración:
#  1. DATABASE_URL (la inyecta Railway en producción; con SSL si no es local)
#  2. PGHOST/PGUSER/... de config.py (desarrollo local, sin SSL)
# ═══════════════════════════════════════════════════════════════════════════
import os
import psycopg2
import psycopg2.extras
from config import Config


class Conexion:
    def __init__(self):
        """
        Prioriza DATABASE_URL (Railway / Render la inyectan automáticamente).
        - LOCAL   : sin SSL (localhost / 127.0.0.1)
        - NUBE    : con sslmode='require' (Railway, Render, etc.)
        - Si no hay DATABASE_URL, usa los parámetros separados de Config.
        """
        db_url = os.getenv("DATABASE_URL")

        if db_url:
            # Modo nube: determina si es local o producción
            es_local = "localhost" in db_url or "127.0.0.1" in db_url
            if es_local:
                self.dblink = psycopg2.connect(db_url)
            else:
                self.dblink = psycopg2.connect(db_url, sslmode="require")
        else:
            # Modo local: conexión por parámetros separados (sin SSL)
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
