"""Contrato de la sesión RCEL (liviano, sin Playwright).

La implementación Playwright vive en app/playwright_session.py; así el worker y
sus tests no arrastran el browser.
"""

from typing import Callable, Iterable, Protocol


class SesionExpirada(Exception):
    """ARCA cerró la sesión; hay que volver a loguear y reintentar."""


def detectar_expiracion(operacion: Callable, paginas: Callable[[], Iterable],
                        es_login: Callable[[str], bool]):
    """Corre `operacion`; si falla y alguna página abierta quedó en el login de
    ARCA, la falla era la sesión expirada (el redirect llega tarde)."""
    try:
        return operacion()
    except Exception as exc:
        if any(p is not None and not p.is_closed() and es_login(p.url) for p in paginas()):
            raise SesionExpirada() from exc
        raise


def primer_camino(caminos: list[Callable]):
    """Prueba cada camino en orden y devuelve el resultado del primero que anda;
    si fallan todos, propaga el error del último."""
    for camino in caminos[:-1]:
        try:
            return camino()
        except Exception:
            continue
    return caminos[-1]()


class RcelSession(Protocol):
    # Ventas (Emitidos) y compras (Recibidos): cada una devuelve una lista de HTML
    # (una por página de la grilla de Mis Comprobantes).
    # `plazo` (time.monotonic, opcional): al pasarlo, los bucles cortan a tiempo.
    def consultar_ventas(self, desde: str, hasta: str,
                         plazo: float | None = None) -> list[str]: ...
    def consultar_compras(self, desde: str, hasta: str,
                          plazo: float | None = None) -> list[str]: ...
    # PDFs de ventas por RCEL: baja los que NO están en `excluir`, hasta `limite`.
    def descargar_pdfs_ventas(self, desde: str, hasta: str, excluir: set,
                              limite: int | None, plazo: float | None = None) -> list[tuple]: ...
    def relogin(self) -> None: ...
    def close(self) -> None: ...
