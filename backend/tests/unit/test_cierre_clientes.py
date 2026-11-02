"""cerrar_sin_error debe llamar al método de cierre correcto de cada cliente aiokafka."""

import asyncio

from observatorio.common.kafka import cerrar_sin_error


class Productor:
    """AIOKafkaProducer / AIOKafkaConsumer: se cierran con stop() y no tienen close()."""

    def __init__(self):
        self.parado = False

    async def stop(self):
        self.parado = True


class Admin:
    """AIOKafkaAdminClient: se cierra con close()."""

    def __init__(self):
        self.cerrado = False

    async def close(self):
        self.cerrado = True


class Roto:
    async def stop(self):
        raise RuntimeError("ya cerrado")


def test_productor_y_consumidor_se_cierran_con_stop():
    productor = Productor()
    asyncio.run(cerrar_sin_error(productor))
    assert productor.parado


def test_admin_se_cierra_con_close():
    admin = Admin()
    asyncio.run(cerrar_sin_error(admin))
    assert admin.cerrado


def test_un_fallo_al_cerrar_no_se_propaga():
    asyncio.run(cerrar_sin_error(Roto()))
