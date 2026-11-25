import pytest

from app.circuit_breaker import CircuitBreaker, CircuitoAbierto


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def _breaker(reloj, **kw):
    kw.setdefault("intervalo_min", 0.0)  # sin throttle salvo que el test lo pida
    return CircuitBreaker(time_fn=reloj, **kw)


def test_permite_mientras_no_haya_fallos():
    reloj = Reloj()
    b = _breaker(reloj)
    b.permitir()  # no lanza


def test_abre_tras_max_fallos():
    reloj = Reloj()
    b = _breaker(reloj, max_fallos=3)
    for _ in range(3):
        b.permitir()
        b.fallo()
    with pytest.raises(CircuitoAbierto):
        b.permitir()  # circuito abierto


def test_reabre_tras_cooldown():
    reloj = Reloj()
    b = _breaker(reloj, max_fallos=2, cooldown=100.0)
    for _ in range(2):
        b.permitir()
        b.fallo()
    with pytest.raises(CircuitoAbierto):
        b.permitir()
    reloj.avanzar(101)
    b.permitir()  # pasó el cooldown -> vuelve a permitir


def test_exito_resetea_los_fallos():
    reloj = Reloj()
    b = _breaker(reloj, max_fallos=2)
    b.permitir(); b.fallo()
    b.permitir(); b.exito()        # reset
    b.permitir(); b.fallo()        # vuelve a 1, no abre
    b.permitir()  # no lanza


def test_throttle_bloquea_login_demasiado_seguido():
    reloj = Reloj()
    b = CircuitBreaker(time_fn=reloj, intervalo_min=30.0)
    b.permitir()
    with pytest.raises(CircuitoAbierto):
        b.permitir()  # mismo instante -> throttle
    reloj.avanzar(31)
    b.permitir()  # pasó el intervalo
