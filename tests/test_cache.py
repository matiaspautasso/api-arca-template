from app.cache import TtlCache


def test_set_y_get():
    c = TtlCache(ttl_seconds=10)
    c.set(("23/10/2026", "02/11/2026"), "<html>")
    assert c.get(("23/10/2026", "02/11/2026")) == "<html>"


def test_get_de_clave_inexistente_devuelve_none():
    c = TtlCache(ttl_seconds=10)
    assert c.get(("nada",)) is None


def test_expira_pasado_el_ttl():
    reloj = {"t": 1000.0}
    c = TtlCache(ttl_seconds=10, time_fn=lambda: reloj["t"])
    c.set("k", "v")
    reloj["t"] = 1009.0
    assert c.get("k") == "v"       # dentro del TTL
    reloj["t"] = 1011.0
    assert c.get("k") is None      # expiró
