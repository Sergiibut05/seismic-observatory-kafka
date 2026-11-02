"""Pruebas del supervisor de sesiones (US3, R-13): reloj, sesión y sonda falsos, sin infraestructura."""

import asyncio
import io
import logging
import sys
from types import SimpleNamespace

import pytest

from observatorio.common.health import EstadoSalud
from observatorio.common.logging import FormateadorClaveValor
from observatorio.common.retry import Backoff
from observatorio.common.supervisor import supervisar

INTERVALO = 5
CONFIG = SimpleNamespace(
    backoff=Backoff(1, 2, 30),
    health_probe_interval_seconds=INTERVALO,
    probe_fallos_reinicio=3,
)


@pytest.fixture
def salida():
    return io.StringIO()


@pytest.fixture
def logger(salida):
    log = logging.getLogger(f"prueba.supervisor.{id(salida)}")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorClaveValor("consumer"))
    log.addHandler(manejador)
    return log


class Escenario:
    """Sesiones y sondas guionizadas; al agotar el guion de la sonda se cancela la tarea."""

    def __init__(self, sondas, fallos_apertura=0):
        self.estado = EstadoSalud(["postgres"])
        self.sondas = list(sondas)
        self.fallos_apertura = fallos_apertura
        self.abiertas = []
        self.cerradas = []
        self.esperas = []
        self.salud_en_cada_espera = []

    async def sleep(self, segundos):
        self.esperas.append(segundos)
        self.salud_en_cada_espera.append(self.estado.sano)

    async def abrir(self):
        if self.fallos_apertura:
            self.fallos_apertura -= 1
            raise ConnectionRefusedError("sin servicio")
        sesion = SimpleNamespace(numero=len(self.abiertas) + 1)
        self.abiertas.append(sesion)
        return sesion

    async def cerrar(self, sesion):
        self.cerradas.append(sesion.numero)

    async def sonda(self, sesion):
        if not self.sondas:
            raise asyncio.CancelledError
        resultado = self.sondas.pop(0)
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado

    def ejecutar(self, logger):
        async def principal():
            await supervisar(
                self.abrir,
                self.sonda,
                "postgres",
                self.estado,
                CONFIG,
                cerrar=self.cerrar,
                sleep=self.sleep,
                logger=logger,
            )

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(principal())


def test_una_sesion_que_falla_al_abrir_se_reintenta_con_backoff(logger, salida):
    esc = Escenario([], fallos_apertura=3)
    esc.ejecutar(logger)
    assert esc.esperas[:3] == [1, 2, 4]
    assert len(esc.abiertas) == 1
    texto = salida.getvalue()
    assert texto.count("result=reintento dependency=postgres") == 3
    assert "reason=ConnectionRefusedError" in texto


def test_al_abrir_la_comprobacion_pasa_a_verde(logger, salida):
    esc = Escenario([True])
    assert not esc.estado.sano
    esc.ejecutar(logger)
    assert esc.salud_en_cada_espera[0] is True
    assert "result=listo component=postgres" in salida.getvalue()


def test_una_sesion_sana_no_se_reinicia(logger):
    esc = Escenario([True] * 6)
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 1
    assert esc.cerradas == [1]  # solo el cierre final por cancelación
    assert set(esc.esperas) == {INTERVALO}
    assert all(esc.salud_en_cada_espera)


def test_un_fallo_aislado_no_recrea_la_sesion(logger):
    esc = Escenario([False, True, False, True, False, True])
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 1


def test_el_contador_cuenta_fallos_consecutivos(logger):
    esc = Escenario([False, False, True, False, False, True])
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 1


def test_tres_fallos_consecutivos_recrean_la_sesion(logger, salida):
    esc = Escenario([False, False, False, True, True])
    esc.ejecutar(logger)
    assert [s.numero for s in esc.abiertas] == [1, 2]
    assert esc.cerradas[0] == 1
    assert "action=sesion_recreada" in salida.getvalue()
    assert "fallos=3" in salida.getvalue()


def test_una_excepcion_en_la_sonda_cuenta_como_fallo(logger, salida):
    esc = Escenario([TimeoutError(), OSError("x"), RuntimeError("y"), True])
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 2
    assert "reason=" in salida.getvalue()


def test_un_exito_pone_en_verde_y_reinicia_el_contador(logger, salida):
    esc = Escenario([False, False, True, True])
    esc.ejecutar(logger)
    # Tras cada sonda hay un sleep; el estado visto en el sleep siguiente refleja la sonda anterior.
    # Antes de cada sonda: recién abierta (verde), tras F (rojo), tras F (rojo), tras T (verde), tras T (verde).
    assert esc.salud_en_cada_espera == [True, False, False, True, True]
    assert len(esc.abiertas) == 1


def test_el_aviso_de_fallo_se_registra_una_vez_y_la_recuperacion_otra(logger, salida):
    esc = Escenario([False, False, True])
    esc.ejecutar(logger)
    texto = salida.getvalue()
    assert texto.count("level=WARNING") == 1
    assert texto.count("result=listo component=postgres") == 2  # apertura y recuperación


def test_la_cancelacion_detiene_sin_reintentar_y_cierra_la_sesion(logger, salida):
    esc = Escenario([])  # la primera sonda cancela
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 1
    assert esc.cerradas == [1]
    assert "result=reintento" not in salida.getvalue()


def test_un_fallo_al_cerrar_no_detiene_la_supervision(logger):
    esc = Escenario([False, False, False, True])

    async def cerrar_roto(sesion):
        esc.cerradas.append(sesion.numero)
        raise RuntimeError("ya cerrada")

    esc.cerrar = cerrar_roto
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 2


def test_nunca_se_invoca_sys_exit(logger, monkeypatch):
    def salir(*args, **kwargs):
        raise AssertionError("el supervisor no debe terminar el proceso")

    monkeypatch.setattr(sys, "exit", salir)
    esc = Escenario([False, False, False, False, False, False, True], fallos_apertura=2)
    esc.ejecutar(logger)
    assert len(esc.abiertas) == 3


def test_la_recreacion_tras_fallos_tambien_usa_backoff_si_no_abre(logger):
    esc = Escenario([False, False, False])
    original = esc.abrir
    llamadas = {"n": 0}

    async def abrir_con_fallo():
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise ConnectionRefusedError("aún caído")
        return await original()

    esc.abrir = abrir_con_fallo
    esc.ejecutar(logger)
    # tras la caída: apertura fallida → espera de backoff 1 s antes de reintentar
    assert 1 in esc.esperas
    assert len(esc.abiertas) == 2

def test_sin_registrar_listo_no_duplica_la_linea_de_apertura(logger, salida):
    esc = Escenario([False, False, True])

    async def principal():
        await supervisar(
            esc.abrir, esc.sonda, "postgres", esc.estado, CONFIG,
            cerrar=esc.cerrar, sleep=esc.sleep, logger=logger, registrar_listo=False,
        )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(principal())
    assert "result=listo" not in salida.getvalue()
    assert esc.estado.sano
