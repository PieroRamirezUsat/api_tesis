from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# storage_uri="memory://" es un contador POR PROCESO. Con gunicorn --workers 2
# cada worker llevaba su propio contador y el limite real nunca se alcanzaba
# (confirmado en vivo: 7 intentos seguidos a /auth/login, cero 429). El
# Procfile ahora usa --workers 1 --threads 8 --worker-class gthread para que
# haya un solo proceso (memory:// como contador unico y real) sin perder
# concurrencia. Si el trafico crece y hace falta mas de un proceso, cambiar a
# un backend compartido: storage_uri = os.environ.get("REDIS_URL", "memory://")
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")