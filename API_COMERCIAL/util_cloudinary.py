"""
util_cloudinary.py  —  Subida de imágenes a Cloudinary (TutorMath / API)

Configuración (variables de entorno):
  CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
  ─── O por separado ───
  CLOUDINARY_CLOUD_NAME=tu_cloud
  CLOUDINARY_API_KEY=123456
  CLOUDINARY_API_SECRET=abc...

Si ninguna variable está definida, `cloudinary_configurado()` retorna False
y los uploads vuelven al modo local (filesystem).
"""
import os
import cloudinary
import cloudinary.uploader
import cloudinary.utils


def _configurar():
    """
    Configura el SDK. Soporta CLOUDINARY_URL (formato completo)
    o las tres variables separadas.
    """
    if os.environ.get("CLOUDINARY_URL"):
        return  # El SDK detecta CLOUDINARY_URL automáticamente
    cloudinary.config(
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
        api_key    = os.environ.get("CLOUDINARY_API_KEY",    ""),
        api_secret = os.environ.get("CLOUDINARY_API_SECRET", ""),
        secure     = True,
    )


_configurar()


def cloudinary_configurado() -> bool:
    """True cuando las credenciales están presentes (Railway/producción)."""
    cfg = cloudinary.config()
    return bool(cfg.cloud_name and cfg.api_key and cfg.api_secret)


def subir_imagen(archivo, public_id: str) -> str:
    """
    Sube `archivo` a Cloudinary con el identificador `public_id`.

    Parámetros
    ----------
    archivo   : FileStorage de Flask, path de archivo o bytes.
    public_id : Ej. "tutormath/desarrollos/resp_42"

    Retorna
    -------
    URL HTTPS permanente (str). Lanza Exception si la subida falla.
    """
    resultado = cloudinary.uploader.upload(
        archivo,
        public_id     = public_id,
        overwrite     = True,
        invalidate    = True,   # purga el CDN al reemplazar (evita fotos viejas cacheadas)
        resource_type = "image",
        format        = "jpg",
    )
    return resultado["secure_url"]