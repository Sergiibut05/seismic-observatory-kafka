import asyncio

from observatorio.common.config import ajustes_consumidor, cargar_o_salir
from observatorio.common.logging import configurar_logging
from observatorio.consumer.app import ejecutar


def main() -> None:
    ajustes = cargar_o_salir("consumer", ajustes_consumidor)
    configurar_logging("consumer", ajustes.log_level, ajustes.secretos())
    asyncio.run(ejecutar(ajustes))


if __name__ == "__main__":
    main()
