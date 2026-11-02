import asyncio

from observatorio.common.config import ajustes_productor, cargar_o_salir
from observatorio.common.logging import configurar_logging
from observatorio.producer.app import ejecutar


def main() -> None:
    ajustes = cargar_o_salir("producer", ajustes_productor)
    configurar_logging("producer", ajustes.log_level, ajustes.secretos())
    asyncio.run(ejecutar(ajustes))


if __name__ == "__main__":
    main()
