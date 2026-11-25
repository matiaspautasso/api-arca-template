import pytest

from app.session import SesionExpirada, detectar_expiracion, primer_camino


class FakePage:
    def __init__(self, url: str, cerrada: bool = False):
        self.url = url
        self._cerrada = cerrada

    def is_closed(self) -> bool:
        return self._cerrada


def es_login(url: str) -> bool:
    return "auth.afip" in url


def falla(exc: Exception):
    def op():
        raise exc
    return op


def test_timeout_con_pagina_en_login_se_traduce_a_sesion_expirada():
    paginas = [FakePage("https://portalcf.cloud.afip.gob.ar/portal/app/"),
               FakePage("https://auth.afip.gob.ar/contribuyente_/login.xhtml")]
    with pytest.raises(SesionExpirada):
        detectar_expiracion(falla(TimeoutError("Locator.fill")), lambda: paginas, es_login)


def test_timeout_real_sin_login_se_propaga_tal_cual():
    paginas = [FakePage("https://fes.afip.gob.ar/mcmp/jsp/setearContribuyente.do"),
               FakePage("https://auth.afip.gob.ar/contribuyente_/login.xhtml", cerrada=True)]
    with pytest.raises(TimeoutError):
        detectar_expiracion(falla(TimeoutError("Locator.click")), lambda: paginas, es_login)


def test_camino_principal_falla_usa_el_alternativo():
    caminos = [falla(TimeoutError("buscador")), lambda: "mis-servicios"]
    assert primer_camino(caminos) == "mis-servicios"
