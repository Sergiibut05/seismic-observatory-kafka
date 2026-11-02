"""Logs `clave=valor` (contracts/logs.md): una línea por registro, siempre con `result`."""

import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timezone

# Conjunto cerrado de resultados (en español, ver R-14).
RESULTADOS = frozenset(
    {
        "publicado",
        "persistido",
        "omitido",
        "rechazado",
        "error",
        "iniciado",
        "listo",
        "reintento",
        "detenido",
        "info",
    }
)

_NIVELES = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

_ESCAPES = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"})


def _a_texto(valor) -> str:
    if valor is None:
        return "-"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, float):
        return format(valor, "g")
    return str(valor)


def _necesita_comillas(texto: str) -> bool:
    return texto == "" or any(c.isspace() or c in '="\\' for c in texto)


def _formatear_valor(texto: str) -> str:
    if _necesita_comillas(texto):
        return '"' + texto.translate(_ESCAPES) + '"'
    return texto


class FormateadorClaveValor(logging.Formatter):
    """Formatea cualquier `LogRecord` (propio o de librería) como una línea `clave=valor`."""

    def __init__(self, service: str, secretos: Iterable[str] = ()):
        super().__init__()
        self.service = service
        # Se ordenan de mayor a menor para que un secreto largo no quede a medias por otro corto.
        self._secretos = sorted({s for s in secretos if s}, key=len, reverse=True)

    def _ocultar(self, texto: str) -> str:
        for secreto in self._secretos:
            texto = texto.replace(secreto, "***")
        return texto

    def _par(self, clave: str, valor) -> str:
        return f"{clave}={_formatear_valor(self._ocultar(_a_texto(valor)))}"

    def format(self, record: logging.LogRecord) -> str:
        instante = datetime.fromtimestamp(record.created, tz=timezone.utc)
        ts = instante.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"
        result = getattr(record, "result", None)
        propio = result is not None
        if not propio:
            result = "error" if record.levelno >= logging.ERROR else "info"
        partes = [
            self._par("ts", ts),
            self._par("level", record.levelname),
            self._par("service", self.service),
            self._par("result", result),
        ]
        for clave, valor in getattr(record, "campos", {}).items():
            partes.append(self._par(clave, valor))
        if not propio:
            partes.append(self._par("msg", record.getMessage()))
        if record.exc_info:
            partes.append(self._par("exc", self.formatException(record.exc_info)))
        return " ".join(partes)


def registrar(
    logger: logging.Logger,
    result: str,
    nivel: str = "INFO",
    exc_info=None,
    **campos,
) -> None:
    """Escribe un registro con `result` del conjunto cerrado y los campos dados, en orden."""
    if result not in RESULTADOS:
        raise ValueError(f"result fuera del conjunto cerrado: {result!r}")
    logger.log(
        _NIVELES[nivel.upper()],
        "",
        extra={"result": result, "campos": campos},
        exc_info=exc_info,
    )


def configurar_logging(service: str, nivel: str = "INFO", secretos: Iterable[str] = ()) -> None:
    """Instala el formateador en el logger raíz: todo (aiokafka, psycopg, uvicorn) sale igual."""
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorClaveValor(service, secretos))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(_NIVELES[nivel.upper()])
