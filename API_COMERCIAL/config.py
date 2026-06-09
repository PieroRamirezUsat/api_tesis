# API_COMERCIAL/config.py
import os
from dotenv import load_dotenv

# Carga el .env si existe (local dev). En Railway, las vars ya están en el entorno.
load_dotenv()

class Config:
    """
    Configuración para la BD.
    Railway inyecta DATABASE_URL automáticamente (ver conexionBD.py).
    En local usa los parámetros separados como fallback.
    """
    DB_HOST     = os.getenv("PGHOST",     "127.0.0.1")
    DB_PORT     = os.getenv("PGPORT",     "5432")
    DB_USER     = os.getenv("PGUSER",     "postgres")
    DB_PASSWORD = os.getenv("PGPASSWORD", "hola1")
    DB_NAME     = os.getenv("PGDATABASE", "bd_ejemplo")


class SecretKey:
    # ⚠️  Cambia esto con la variable JWT_SECRET_KEY en Railway/producción
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "claveSuperSecreta2025")


class Host:
    URL_APP = os.getenv("URL_APP", "http://127.0.0.1:3008/")
