import datetime as dt

from scripts.sync_semanal import rango_mes_anterior


def test_rango_arranca_el_primero_del_mes_pasado():
    desde, hasta = rango_mes_anterior(dt.date(2026, 11, 8))
    assert desde == "01/10/2026"
    assert hasta == "08/11/2026"


def test_rango_cruza_año():
    desde, hasta = rango_mes_anterior(dt.date(2026, 1, 15))
    assert desde == "01/12/2025"
    assert hasta == "15/01/2026"


def _trabajo(estado, **tipos):
    return {"trabajo": {"estado": estado, "tipos": {
        t: {"estado": e, "sincronizados": None, "mensaje": None} for t, e in tipos.items()}}}


def _cron(monkeypatch, estados):
    """Corre el cron con la API falsa: `estados` son las respuestas sucesivas de /sync/estado."""
    from scripts import sync_semanal

    lanzados = []
    monkeypatch.setenv("SYNC_API_URL", "http://api")
    monkeypatch.setattr(sync_semanal, "lanzar", lambda base, token, desde, hasta: lanzados.append((desde, hasta)))
    respuestas = iter(estados)
    monkeypatch.setattr(sync_semanal, "leer_estado", lambda base: next(respuestas))
    monkeypatch.setattr(sync_semanal, "esperar", lambda segundos: None)
    return sync_semanal.main(), lanzados


def test_cron_lanza_la_consulta_completa_y_espera_que_termine(monkeypatch):
    codigo, lanzados = _cron(monkeypatch, [
        _trabajo("en_curso", ventas="ok", compras="en_curso", pdfs="pendiente"),
        _trabajo("terminado", ventas="ok", compras="ok", pdfs="ok"),
    ])
    assert len(lanzados) == 1
    assert codigo == 0


def test_cron_falla_si_algun_tipo_fallo(monkeypatch):
    codigo, _ = _cron(monkeypatch, [_trabajo("terminado", ventas="ok", compras="fallo", pdfs="ok")])
    assert codigo == 1


def test_cron_falla_si_la_consulta_no_termina_a_tiempo(monkeypatch):
    from scripts import sync_semanal

    monkeypatch.setattr(sync_semanal, "MAX_CONSULTAS_DE_ESTADO", 3)
    codigo, _ = _cron(monkeypatch, [_trabajo("en_curso", ventas="en_curso")] * 3)
    assert codigo == 1
