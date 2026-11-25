"""Protocolo del cliente RCEL + helpers de localización resiliente.

El cliente que consume la API es el worker (app/worker.py), que implementa este
protocolo. La navegación real vive en app/playwright_session.py.
"""

from __future__ import annotations

from typing import Protocol

from playwright.sync_api import Locator, Page


class RcelClient(Protocol):
    """Seam inyectable en los endpoints (en tests se reemplaza por un fake)."""

    def consultar_ventas(self, desde: str, hasta: str,
                         plazo: float | None = None) -> list[str]: ...
    def consultar_compras(self, desde: str, hasta: str,
                          plazo: float | None = None) -> list[str]: ...
    def descargar_pdfs_ventas(self, desde: str, hasta: str, excluir: set,
                              limite: int | None, plazo: float | None = None) -> list[tuple]: ...
    def cerrar_sesion(self) -> None: ...


def _build(page: Page, spec: dict) -> Locator:
    by = spec["by"]
    if by == "css":
        return page.locator(spec["value"])
    if by == "role":
        return page.get_by_role(spec["role"], name=spec.get("name"),
                                exact=spec.get("exact", False))
    if by == "label":
        return page.get_by_label(spec["text"], exact=spec.get("exact", False))
    if by == "text":
        return page.get_by_text(spec["text"], exact=spec.get("exact", False))
    if by == "placeholder":
        return page.get_by_placeholder(spec["text"])
    raise ValueError(f"spec 'by' desconocido: {by}")


def _first(page: Page, specs: list[dict], timeout: int = 5000) -> Locator:
    """Prueba los candidatos EN ORDEN; devuelve el primero visible o falla."""
    for spec in specs:
        loc = _build(page, spec).first
        try:
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    raise RuntimeError(
        "No se encontró ningún selector esperado (¿cambió la UI de ARCA?). "
        "Revisá app/rcel_selectors.py."
    )
