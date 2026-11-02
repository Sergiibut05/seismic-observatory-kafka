import uvicorn

from observatorio.api.main import crear_app
from observatorio.common.config import ajustes_api, cargar_o_salir
from observatorio.common.logging import configurar_logging


def main() -> None:
    ajustes = cargar_o_salir("api", ajustes_api)
    configurar_logging("api", ajustes.log_level, ajustes.secretos())
    # log_config=None y access_log=False: uvicorn no imprime sus propias líneas (rompen SC-009).
    uvicorn.run(crear_app(ajustes), host="0.0.0.0", port=8000, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
