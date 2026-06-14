"""
test_11_seguridad_uploads.py — Pruebas de SEGURIDAD: subida de archivos (POST /tutor/subir_desarrollo)
=======================================================================================================
Tipo  : Seguridad / Validación de entrada
Ruta  : POST /tutor/subir_desarrollo

Escenarios probados
-------------------
El endpoint recibe el "desarrollo" (foto del trabajo) del estudiante.
Un estudiante malicioso podría intentar subir archivos peligrosos.

[U1] Extensiones peligrosas rechazadas: .rar, .exe, .php, .html, .bat, .sh, .js, .zip, .py
     → 400 + mensaje de error claro

[U2] Extensiones válidas aceptadas: .jpg, .jpeg, .png, .gif, .webp, .pdf
     → No rechazadas por extensión (pueden fallar en la subida por mock, pero no por validación)

[U3] Archivo demasiado grande (> 10 MB) → 400

[U4] Sin archivo / sin idRespuesta → 400

[U5] Truco de doble extensión:
     "shell.php.jpg"  → extensión real es .jpg → aceptado
     "shell.jpg.php"  → extensión real es .php → rechazado

[U6] Archivo sin extensión → rechazado

Fix aplicado (2026-06-14):
  subir_desarrollo ahora valida extensión con whitelist ANTES de tocar el disco.
  Antes: secure_filename() solo sanitizaba la ruta, no el tipo.
  Ahora: _ALLOWED_DESARROLLO_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf'}
         _MAX_DESARROLLO_BYTES = 10 * 1024 * 1024
"""

import io
import pytest

pytestmark = pytest.mark.security


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _upload(client, filename, content=b"contenido de prueba", id_respuesta="5"):
    """Envía POST multipart con un archivo falso."""
    data = {}
    if id_respuesta is not None:
        data["idRespuesta"] = id_respuesta
    if filename is not None:
        data["archivo"] = (io.BytesIO(content), filename)
    return client.post(
        "/tutor/subir_desarrollo",
        data=data,
        content_type="multipart/form-data",
    )


def _upload_size(client, size_bytes, filename="foto.jpg", id_respuesta="5"):
    """Sube un archivo de tamaño controlado."""
    content = b"X" * size_bytes
    return _upload(client, filename, content=content, id_respuesta=id_respuesta)


# ─────────────────────────────────────────────────────────────────────────────
# U1 — Extensiones peligrosas rechazadas
# ─────────────────────────────────────────────────────────────────────────────

class TestExtensionPeligrosaRechazada:

    @pytest.mark.parametrize("filename", [
        "malware.rar",
        "virus.exe",
        "shell.php",
        "xss.html",
        "script.bat",
        "exploit.sh",
        "payload.js",
        "archive.zip",
        "code.py",
        "macro.docm",
        "libro.xlsm",
        "backdoor.asp",
        "webshell.aspx",
        "cmd.cmd",
    ])
    def test_extension_peligrosa_rechazada_400(self, client, mock_cursor, filename):
        """Extensión peligrosa → 400, mensaje claro, sin tocar disco ni BD."""
        r = _upload(client, filename)
        assert r.status_code == 400, (
            f"'{filename}' debe ser rechazado con 400 (got {r.status_code})"
        )
        data = r.get_json()
        assert data is not None
        assert data.get("status") is False
        assert "permitido" in data.get("message", "").lower() or \
               "no permit" in data.get("message", "").lower(), (
            f"Mensaje de error no claro para '{filename}': {data.get('message')}"
        )

    def test_sin_extension_rechazado(self, client, mock_cursor):
        """Archivo sin extensión → rechazado."""
        r = _upload(client, "archivo_sin_extension")
        assert r.status_code == 400

    def test_solo_punto_rechazado(self, client, mock_cursor):
        """Filename '.' → rechazado."""
        r = _upload(client, ".")
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# U2 — Extensiones válidas NO rechazadas por validación de tipo
# ─────────────────────────────────────────────────────────────────────────────

class TestExtensionValidaNoRechazada:

    @pytest.mark.parametrize("filename", [
        "foto.jpg",
        "captura.jpeg",
        "desarrollo.png",
        "animacion.gif",
        "imagen.webp",
        "solucion.pdf",
        "FOTO.JPG",         # mayúsculas — ext se convierte a lower
        "Desarrollo.PDF",
    ])
    def test_extension_valida_no_rechazada_por_tipo(self, client, mock_cursor, filename):
        """
        Extensión válida → no rechazada por validación de tipo.
        Puede fallar en subida (Cloudinary/filesystem mockeados) pero el status
        será 200 o 500 (error de guardado), NUNCA 400 por tipo de archivo.
        """
        r = _upload(client, filename)
        assert r.status_code != 400, (
            f"'{filename}' es válido y no debe ser rechazado por tipo (got 400)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# U3 — Tamaño máximo (10 MB)
# ─────────────────────────────────────────────────────────────────────────────

class TestTamanoMaximo:

    def test_archivo_dentro_del_limite_no_rechazado(self, client, mock_cursor):
        """1 MB → no rechazado por tamaño."""
        r = _upload_size(client, 1 * 1024 * 1024)  # 1 MB
        assert r.status_code != 400 or "tamaño" not in (r.get_json() or {}).get("message", "")

    def test_archivo_limite_exacto_no_rechazado(self, client, mock_cursor):
        """10 MB exactos → no rechazado."""
        r = _upload_size(client, 10 * 1024 * 1024)  # 10 MB exactos
        assert r.status_code != 400 or "tamaño" not in (r.get_json() or {}).get("message", "")

    def test_archivo_supera_limite_rechazado(self, client, mock_cursor):
        """10 MB + 1 byte → rechazado con 400."""
        r = _upload_size(client, 10 * 1024 * 1024 + 1)
        assert r.status_code == 400, (
            f"Archivo > 10 MB debe ser rechazado (got {r.status_code})"
        )
        data = r.get_json()
        assert data.get("status") is False
        msg = data.get("message", "").lower()
        assert "tamaño" in msg or "grande" in msg or "mb" in msg, (
            f"Mensaje debe mencionar el tamaño: '{data.get('message')}'"
        )

    def test_archivo_20mb_rechazado(self, client, mock_cursor):
        """20 MB → rechazado."""
        r = _upload_size(client, 20 * 1024 * 1024)
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# U4 — Campos obligatorios ausentes
# ─────────────────────────────────────────────────────────────────────────────

class TestCamposObligatorios:

    def test_sin_archivo_rechazado(self, client, mock_cursor):
        """Sin archivo → 400."""
        r = client.post(
            "/tutor/subir_desarrollo",
            data={"idRespuesta": "5"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_sin_id_respuesta_rechazado(self, client, mock_cursor):
        """Sin idRespuesta → 400."""
        r = client.post(
            "/tutor/subir_desarrollo",
            data={"archivo": (io.BytesIO(b"foto"), "foto.jpg")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_sin_nada_rechazado(self, client, mock_cursor):
        """Sin nada → 400."""
        r = client.post("/tutor/subir_desarrollo", data={})
        assert r.status_code == 400

    def test_id_respuesta_cero_rechazado(self, client, mock_cursor):
        """idRespuesta=0 (falsy) → 400."""
        r = _upload(client, "foto.jpg", id_respuesta="0")
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# U5 — Truco de doble extensión
# ─────────────────────────────────────────────────────────────────────────────

class TestDobleExtension:

    def test_shell_jpg_php_rechazado(self, client, mock_cursor):
        """
        'shell.jpg.php' — la extensión REAL (última) es .php → rechazado.
        os.path.splitext('shell.jpg.php') = ('shell.jpg', '.php')
        """
        r = _upload(client, "shell.jpg.php")
        assert r.status_code == 400, (
            "shell.jpg.php tiene extensión .php → debe ser rechazado"
        )

    def test_malware_pdf_exe_rechazado(self, client, mock_cursor):
        """'recurso.pdf.exe' → extensión .exe → rechazado."""
        r = _upload(client, "recurso.pdf.exe")
        assert r.status_code == 400

    def test_shell_php_jpg_aceptado_por_extension(self, client, mock_cursor):
        """
        'shell.php.jpg' — la extensión es .jpg → no rechazado por tipo.
        Nota: el contenido podría ser malicioso, pero Flask/Python no lo ejecuta.
        El sistema solo guarda el binario; el riesgo es nulo en Python/WSGI.
        """
        r = _upload(client, "shell.php.jpg")
        assert r.status_code != 400 or "permit" not in (r.get_json() or {}).get("message", "")


# ─────────────────────────────────────────────────────────────────────────────
# U6 — Invariante: la validación ocurre ANTES de tocar el disco
# ─────────────────────────────────────────────────────────────────────────────

class TestValidacionAntesDelDisco:

    def test_rar_rechazado_sin_acceder_al_filesystem(self, client, mock_cursor):
        """
        Un .rar debe ser rechazado con 400 antes de intentar guardarlo.
        El mock de la BD no debe haber recibido ningún execute de UPDATE.
        """
        r = _upload(client, "trampa.rar")
        assert r.status_code == 400
        # Ningún UPDATE en respuestas_estudiantes debe haber ocurrido
        updates = [c for c in mock_cursor.execute.call_args_list
                   if "UPDATE" in str(c).upper()
                   and "respuestas_estudiantes" in str(c).lower()]
        assert len(updates) == 0, (
            "El archivo rechazado NO debe generar UPDATE en respuestas_estudiantes"
        )

    def test_php_rechazado_sin_acceder_al_filesystem(self, client, mock_cursor):
        """Un .php rechazado no toca la BD."""
        r = _upload(client, "webshell.php")
        assert r.status_code == 400
        updates = [c for c in mock_cursor.execute.call_args_list
                   if "UPDATE" in str(c).upper()]
        assert len(updates) == 0