import pytest

import app.playwright_session as ps
from app.config import Settings


class FakePage:
    url = "https://auth.afip.gob.ar/contribuyente_/login.xhtml?x=1"

    def title(self):
        return "Login"

    def is_closed(self):
        return False


class FakeContext:
    def __init__(self):
        self.pages = [FakePage()]

    def set_default_timeout(self, ms):
        pass

    def close(self):
        pass


class FakeBrowser:
    def new_context(self, **_):
        return FakeContext()

    def close(self):
        pass


class FakePlaywright:
    def __init__(self):
        self.detenido = False
        self.chromium = self

    def launch(self, **_):
        return FakeBrowser()

    def stop(self):
        self.detenido = True


@pytest.fixture
def arranques(monkeypatch):
    creados: list[FakePlaywright] = []

    class FakeSyncPlaywright:
        def start(self):
            if creados and not creados[-1].detenido:
                raise RuntimeError("Sync API inside the asyncio loop")
            creados.append(FakePlaywright())
            return creados[-1]

    monkeypatch.setattr(ps, "sync_playwright", FakeSyncPlaywright)
    return creados


def test_login_fallido_no_deja_playwright_colgado(arranques, monkeypatch):
    sesion = ps.PlaywrightRcelSession(Settings())

    def login_que_falla():
        raise TimeoutError("networkidle")

    monkeypatch.setattr(sesion, "_login", login_que_falla)

    with pytest.raises(TimeoutError):
        sesion._ensure()
    # El segundo intento arranca limpio (antes: 'Sync API inside the asyncio loop').
    with pytest.raises(TimeoutError):
        sesion._ensure()

    assert len(arranques) == 2
