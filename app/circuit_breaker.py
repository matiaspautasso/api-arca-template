"""Circuit breaker para proteger el LOGIN contra ARCA (dominio puro, testeable).

Objetivo: no saturar ni bloquear la sesión con reintentos de login.
  - Throttle: no se permite un nuevo login antes de `intervalo_min` segundos.
  - Corte: tras `max_fallos` logins fallidos seguidos, abre el circuito por
    `cooldown` segundos y NO deja intentar (falla rápido).
  - Un login exitoso resetea el contador.

No hace I/O ni duerme: solo decide si se PUEDE intentar. El reloj es inyectable.
"""

import time


class CircuitoAbierto(Exception):
    """No se intenta el login ahora (circuito abierto o throttle activo)."""


class CircuitBreaker:
    def __init__(self, max_fallos: int = 3, cooldown: float = 3600.0,
                 intervalo_min: float = 30.0, time_fn=time.monotonic):
        self._max_fallos = max_fallos
        self._cooldown = cooldown
        self._intervalo_min = intervalo_min
        self._time = time_fn
        self._fallos = 0
        self._abierto_hasta = 0.0
        self._ultimo_intento: float | None = None

    def permitir(self) -> None:
        """Lanza CircuitoAbierto si no corresponde intentar; si no, registra el intento."""
        ahora = self._time()
        if ahora < self._abierto_hasta:
            restante = round(self._abierto_hasta - ahora)
            raise CircuitoAbierto(
                f"Circuito abierto tras {self._fallos} fallos de login; "
                f"reintento posible en {restante}s."
            )
        if (self._ultimo_intento is not None
                and ahora - self._ultimo_intento < self._intervalo_min):
            espera = round(self._intervalo_min - (ahora - self._ultimo_intento))
            raise CircuitoAbierto(
                f"Login demasiado seguido; esperá {espera}s para no saturar ARCA."
            )
        self._ultimo_intento = ahora

    def exito(self) -> None:
        self._fallos = 0
        self._abierto_hasta = 0.0

    def fallo(self) -> None:
        self._fallos += 1
        if self._fallos >= self._max_fallos:
            self._abierto_hasta = self._time() + self._cooldown
