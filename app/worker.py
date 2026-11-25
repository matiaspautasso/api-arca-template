"""Worker in-process: un hilo dueño de UNA sesión RCEL caliente.

- Serializa los pedidos (el portal es stateful; no se maneja en paralelo).
- Cachea `consultar` por (desde, hasta) con TTL.
- Reintenta con relogin si la sesión expiró.
- TODO el trabajo de Playwright corre en el hilo del worker (la sync API no
  admite llamadas cross-thread), incluido el cierre de la sesión.
- Límite por pedido (4 min). Si tras el límite + un margen el hilo sigue trabado,
  Playwright quedó colgado: no se puede cerrar desde otro hilo ni abrir una sesión
  paralela (dos sesiones de clave fiscal), así que se termina el proceso y Railway
  lo reinicia.
"""

import os
import queue
import threading
import time
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Callable

from app.cache import TtlCache
from app.circuit_breaker import CircuitBreaker
from app.session import RcelSession, SesionExpirada

_SENTINEL = object()


def _terminar_proceso() -> None:
    print("[worker] Playwright colgado: se termina el proceso para que Railway lo reinicie.",
          flush=True)
    os._exit(1)


class RcelWorker:
    def __init__(self, session: RcelSession, ttl_seconds: float = 300.0,
                 job_timeout: float = 240.0, breaker: CircuitBreaker | None = None,
                 margen_colgado: float = 60.0,
                 al_colgarse: Callable[[], None] = _terminar_proceso):
        self._session = session
        self._cache_ttl = ttl_seconds
        self._cache = TtlCache(ttl_seconds)
        self._job_timeout = job_timeout
        self._margen_colgado = margen_colgado
        self._al_colgarse = al_colgarse
        # Protege el login: throttle + corte tras fallos seguidos (no saturar ARCA).
        self._breaker = breaker or CircuitBreaker()
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._stopped = False

    # -------------------------------------------------------- ciclo de vida
    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._queue.put(_SENTINEL)
        self._thread.join(timeout=30)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is _SENTINEL:
                try:
                    self._session.close()
                except Exception:  # noqa: BLE001 - cerrar es best-effort
                    pass
                return
            fn, fut = job
            try:
                fut.set_result(fn())
            except Exception as exc:  # noqa: BLE001 - se propaga al caller vía future
                fut.set_exception(exc)

    # ----------------------------------------------------------- utilidades
    def _submit(self, fn: Callable, plazo: float | None = None):
        """Encola `fn` para correr en el hilo del worker y espera su resultado, hasta
        el límite por pedido o el `plazo` (time.monotonic), lo que llegue antes."""
        fut: Future = Future()
        self._queue.put((fn, fut))
        espera = self._job_timeout
        if plazo is not None:
            espera = max(0.0, min(espera, plazo - time.monotonic()))
        try:
            return fut.result(timeout=espera)
        except FutureTimeout:
            # Pasó el límite: se informa igual. Si ni con el margen termina (cada
            # acción de Playwright corta a los 30 s), el hilo quedó colgado.
            try:
                fut.exception(timeout=self._margen_colgado)
            except FutureTimeout:
                self._al_colgarse()
            raise

    def _reintentar(self, fn: Callable):
        """Corre `fn`; si la sesión expiró, reloguea (pasando por el breaker) y
        reintenta UNA vez. Si el breaker no permite el login, no reintenta."""
        try:
            return fn()
        except SesionExpirada:
            self._breaker.permitir()      # throttle / corte: puede lanzar CircuitoAbierto
            try:
                self._session.relogin()
            except Exception:
                self._breaker.fallo()
                raise
            self._breaker.exito()
            return fn()

    # -------------------------------------------------------- API (RcelClient)
    def _consultar(self, tipo: str, desde: str, hasta: str,
                   plazo: float | None) -> list[str]:
        clave = (tipo, desde, hasta)
        cacheado = self._cache.get(clave)
        if cacheado is not None:
            return cacheado
        fn = (self._session.consultar_ventas if tipo == "ventas"
              else self._session.consultar_compras)
        paginas = self._submit(lambda: self._reintentar(lambda: fn(desde, hasta, plazo)),
                               plazo)
        self._cache.set(clave, paginas)
        return paginas

    def cerrar_sesion(self) -> None:
        """Cierra la sesión de ARCA (en el hilo del worker) y vacía la caché: la
        próxima consulta loguea de nuevo. ARCA vence las sesiones sin avisar y sus
        apps no siempre redirigen al login, así que no se reusa una sesión vieja."""
        def cerrar():
            try:
                self._session.close()
            except Exception:  # noqa: BLE001 - cerrar es best-effort
                pass
        self._submit(cerrar)
        self._cache = TtlCache(self._cache_ttl)

    # `plazo` (time.monotonic): la sesión lo recibe para cortar sus bucles a tiempo.
    def consultar_ventas(self, desde: str, hasta: str,
                         plazo: float | None = None) -> list[str]:
        return self._consultar("ventas", desde, hasta, plazo)

    def consultar_compras(self, desde: str, hasta: str,
                          plazo: float | None = None) -> list[str]:
        return self._consultar("compras", desde, hasta, plazo)

    def descargar_pdfs_ventas(self, desde: str, hasta: str, excluir: set,
                              limite: int | None, plazo: float | None = None) -> list[tuple]:
        """Sin caché: cada llamada baja solo los PDF que faltan (excluir = ya en DB)."""
        return self._submit(lambda: self._reintentar(
            lambda: self._session.descargar_pdfs_ventas(desde, hasta, excluir, limite, plazo)),
            plazo)
