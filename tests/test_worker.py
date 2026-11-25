import pytest

from app.circuit_breaker import CircuitBreaker, CircuitoAbierto
from app.session import SesionExpirada
from app.worker import RcelWorker


class FakeSession:
    """Sesión falsa: sin Playwright. Registra llamadas y puede simular expiración."""

    def __init__(self, expira_una_vez: bool = False, relogin_falla: bool = False):
        self.ventas = 0
        self.compras = 0
        self.relogins = 0
        self.cerrada = False
        self._expira = expira_una_vez
        self._relogin_falla = relogin_falla

    def consultar_ventas(self, desde, hasta, plazo=None):
        self.plazo = plazo
        self.ventas += 1
        if self._expira:
            self._expira = False
            raise SesionExpirada()
        return [f"<v {desde}-{hasta}>"]

    def consultar_compras(self, desde, hasta, plazo=None):
        self.compras += 1
        if self._expira:
            self._expira = False
            raise SesionExpirada()
        return [f"<c {desde}-{hasta}>", "<c2>"]

    def relogin(self):
        self.relogins += 1
        if self._relogin_falla:
            raise RuntimeError("login falló")

    def close(self):
        self.cerrada = True


@pytest.fixture
def hacer_worker():
    creados = []

    def make(session, breaker=None):
        w = RcelWorker(session, breaker=breaker)
        w.start()
        creados.append(w)
        return w

    yield make
    for w in creados:
        w.stop()


def test_consultar_ventas_devuelve_las_paginas(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    assert w.consultar_ventas("23/10/2026", "02/11/2026") == ["<v 23/10/2026-02/11/2026>"]
    assert s.ventas == 1


def test_segunda_consulta_identica_sale_de_cache(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    w.consultar_ventas("a", "b")
    w.consultar_ventas("a", "b")
    assert s.ventas == 1  # la 2da salió de la caché


def test_relogin_y_reintento_si_la_sesion_expira(hacer_worker):
    s = FakeSession(expira_una_vez=True)
    w = hacer_worker(s)
    assert w.consultar_ventas("a", "b") == ["<v a-b>"]
    assert s.relogins == 1
    assert s.ventas == 2  # 1 intento fallido + 1 reintento OK


def test_stop_cierra_la_sesion(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    w.consultar_ventas("a", "b")
    w.stop()
    assert s.cerrada is True


def test_consultar_compras_devuelve_las_paginas(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    assert w.consultar_compras("a", "b") == ["<c a-b>", "<c2>"]
    assert s.compras == 1


def test_compras_segunda_identica_sale_de_cache(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    w.consultar_compras("a", "b")
    w.consultar_compras("a", "b")
    assert s.compras == 1


def test_ventas_y_compras_no_comparten_cache(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    w.consultar_ventas("a", "b")
    w.consultar_compras("a", "b")  # mismas fechas, distinto tipo -> no colisiona
    assert s.ventas == 1 and s.compras == 1


def test_breaker_corta_tras_logins_fallidos(hacer_worker):
    # relogin siempre falla -> el breaker abre y deja de intentar.
    s = FakeSession(expira_una_vez=True, relogin_falla=True)
    breaker = CircuitBreaker(max_fallos=1, intervalo_min=0.0)
    w = hacer_worker(s, breaker=breaker)
    with pytest.raises(RuntimeError):          # 1er intento: relogin falla
        w.consultar_ventas("a", "b")
    s._expira = True                            # forzar otra expiración
    with pytest.raises(CircuitoAbierto):        # breaker abierto: no reintenta login
        w.consultar_ventas("a", "b")
    assert s.relogins == 1                       # no volvió a loguear


# ------------------------------------------------------------ límite y cuelgues
import threading  # noqa: E402
from concurrent.futures import TimeoutError as FutureTimeout  # noqa: E402


class FakeSessionLenta(FakeSession):
    """Sesión que tarda `segundos` (None = se cuelga hasta que la liberen)."""

    def __init__(self, segundos: float | None):
        super().__init__()
        self.segundos = segundos
        self.liberar = threading.Event()

    def consultar_ventas(self, desde, hasta, plazo=None):
        self.plazo = plazo
        self.liberar.wait(self.segundos)
        return ["<v>"]


def _worker_con_limite(sesion, colgados):
    w = RcelWorker(sesion, job_timeout=0.2, margen_colgado=0.3,
                   al_colgarse=lambda: colgados.append(True))
    w.start()
    return w


def test_si_playwright_queda_colgado_tras_el_limite_avisa_el_cuelgue():
    colgados = []
    s = FakeSessionLenta(segundos=None)
    w = _worker_con_limite(s, colgados)
    try:
        with pytest.raises(FutureTimeout):
            w.consultar_ventas("a", "b")
        assert colgados == [True]
    finally:
        s.liberar.set()
        w.stop()


def test_si_termina_dentro_del_margen_no_es_un_cuelgue():
    colgados = []
    s = FakeSessionLenta(segundos=0.3)   # pasa el límite (0,2) pero no el margen
    w = _worker_con_limite(s, colgados)
    try:
        with pytest.raises(FutureTimeout):
            w.consultar_ventas("a", "b")
        assert colgados == []
    finally:
        w.stop()


def test_el_plazo_de_la_consulta_corta_antes_que_el_limite_por_pedido():
    import time
    s = FakeSessionLenta(segundos=None)
    w = RcelWorker(s, job_timeout=30, margen_colgado=0.5, al_colgarse=lambda: None)
    w.start()
    try:
        plazo = time.monotonic() + 0.2
        antes = time.monotonic()
        with pytest.raises(FutureTimeout):
            w.consultar_ventas("a", "b", plazo=plazo)
        # Cortó en el plazo (0,2 s) + el margen (0,5 s), no a los 30 s.
        assert time.monotonic() - antes < 2
        assert s.plazo == plazo     # la sesión lo recibe para cortar sus bucles
    finally:
        s.liberar.set()
        w.stop()


def test_cerrar_sesion_la_cierra_y_la_proxima_consulta_no_sale_de_cache(hacer_worker):
    s = FakeSession()
    w = hacer_worker(s)
    w.consultar_ventas("a", "b")
    w.cerrar_sesion()
    assert s.cerrada
    w.consultar_ventas("a", "b")
    assert s.ventas == 2   # con la sesión nueva se vuelve a consultar ARCA
