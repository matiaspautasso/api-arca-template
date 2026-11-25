"""Sesión ARCA CALIENTE con Playwright (adapter I/O, no unit-test).

Loguea UNA vez con clave fiscal y mantiene el browser/contexto vivos. Tanto
ventas (Mis Comprobantes > Emitidos) como compras (> Recibidos) usan la MISMA
sesión (SSO): se abre la app Mis Comprobantes una vez y cada consulta entra a su
sección, filtra y lee la grilla. Si ARCA cerró la sesión, lanza SesionExpirada
para que el worker reloguee y reintente.

IMPORTANTE: todos sus métodos se invocan desde el ÚNICO hilo del worker.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

from app import rcel_selectors as SEL
from app.config import Settings
from app.rcel_client import _first
from app.rcel_parsing import PdfRef, parse_rcel_pdf_refs
from app.session import SesionExpirada, detectar_expiracion, primer_camino


MARGEN_PARA_GUARDAR_S = 10


class PlaywrightRcelSession:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._pw = None
        self._browser = None
        self._context = None
        self._portal: Page | None = None    # portal (para abrir Mis Comprobantes)
        self._portal_url = ""
        self._mcmp: Page | None = None       # app Mis Comprobantes (ventas+compras)
        self._mcmp_home = ""
        self._rcel: Page | None = None       # app RCEL (PDF de ventas)
        self._rcel_menu = ""
        self._plazo: float | None = None    # de la consulta en curso (time.monotonic)

    # ---------------------------------------------------------- login/arranque
    def _ensure(self) -> None:
        if self._portal is not None:
            return
        self._pw = sync_playwright().start()
        args = ["--no-sandbox", "--disable-dev-shm-usage"] if self.s.no_sandbox else []
        self._browser = self._pw.chromium.launch(headless=self.s.headless, args=args)
        self._context = self._browser.new_context(accept_downloads=True)
        # Cada acción (clic, navegación, espera) corta a los 30 s: ningún paso espera para siempre.
        self._context.set_default_timeout(30000)
        try:
            self._login()
        except Exception:
            # Diagnóstico sin credenciales: en qué pantalla quedó el login.
            for p in self._context.pages:
                try:
                    print(f"[login] falló en {p.url.split('?')[0]} | título: {p.title()}", flush=True)
                except Exception:  # noqa: BLE001 - el diagnóstico es best-effort
                    pass
            # Sin esto, Playwright queda vivo y el próximo _ensure falla con
            # 'Sync API inside the asyncio loop' hasta reiniciar el backend.
            self.close()
            raise

    def _login(self) -> None:
        """Clave fiscal -> portal. NO entra a RCEL: ventas y compras salen de Mis
        Comprobantes, que se abre luego desde el portal (misma sesión SSO)."""
        page = self._context.new_page()
        page.goto(self.s.login_url, wait_until="domcontentloaded")
        _first(page, SEL.LOGIN["cuit_input"]).fill(self.s.cuit)
        _first(page, SEL.LOGIN["btn_siguiente"]).click()
        _first(page, SEL.LOGIN["password_input"]).fill(self.s.password)
        _first(page, SEL.LOGIN["btn_ingresar"]).click()
        # Sin 'networkidle': desde Railway el portal nunca deja de hacer pedidos y esa
        # espera cortaba logins exitosos (2026-11-20). Alcanza con ver el buscador.
        # Precondición de login OK: el buscador del portal está visible.
        page.locator(SEL.MCMP["buscador"]).wait_for(state="visible", timeout=60000)
        self._portal = page
        self._portal_url = page.url

    # -------------------------------------------------------------- API pública
    def consultar_ventas(self, desde: str, hasta: str,
                         plazo: float | None = None) -> list[str]:
        """Mis Comprobantes > Emitidos en [desde, hasta], TODOS los tipos.
        Devuelve el HTML de cada página de la grilla (parse_ventas procesa una)."""
        self._plazo = plazo
        return self._vigilado(lambda: self._consultar_mcmp(
            SEL.MCMP["emitidos"], desde, hasta,
            SEL.MCMP["cols_ventas"], tipos=SEL.MCMP["tipos_ventas"]))

    def consultar_compras(self, desde: str, hasta: str,
                          plazo: float | None = None) -> list[str]:
        """Mis Comprobantes > Recibidos, tipos A/B/C, Recibo B y Nota de Crédito A."""
        self._plazo = plazo
        return self._vigilado(lambda: self._consultar_mcmp(
            SEL.MCMP["recibidos"], desde, hasta,
            SEL.MCMP["cols_compras"], tipos=SEL.MCMP["tipos_compras"]))

    def _queda(self) -> float:
        """Segundos hasta el plazo de la consulta (infinito si no hay plazo)."""
        return float("inf") if self._plazo is None else self._plazo - time.monotonic()

    def _vigilado(self, operacion):
        """Si la operación falla y alguna pestaña terminó en el login de ARCA, la
        causa fue la sesión expirada: SesionExpirada para que el worker reloguee."""
        try:
            return detectar_expiracion(
                operacion, lambda: [self._portal, self._mcmp, self._rcel], self._es_login)
        except Exception:
            self._registrar_pestanas()
            raise

    def _registrar_pestanas(self) -> None:
        """Diagnóstico sin credenciales: en qué pantalla quedó cada pestaña."""
        for nombre, p in (("portal", self._portal), ("mcmp", self._mcmp), ("rcel", self._rcel)):
            if p is None or p.is_closed():
                continue
            try:
                print(f"[falla] {nombre}: {p.url.split('?')[0]} | título: {p.title()}", flush=True)
            except Exception:  # noqa: BLE001 - el diagnóstico es best-effort
                pass

    # ------------------------------------------------------- Mis Comprobantes
    def _consultar_mcmp(self, seccion: str, desde: str, hasta: str,
                        columnas: list[str], tipos: list[str]) -> list[str]:
        self._ensure()
        self._abrir_mcmp()
        mc = self._mcmp
        # Reset a la home de la app y entrada a la sección pedida (Emitidos/Recibidos).
        mc.goto(self._mcmp_home, wait_until="domcontentloaded")
        if self._es_login(mc.url):
            raise SesionExpirada()
        mc.get_by_text(seccion, exact=True).first.click()
        mc.wait_for_load_state("networkidle")
        self._filtrar(mc, desde, hasta, tipos)
        mc.get_by_role("button", name=SEL.MCMP["buscar"]).click()
        mc.wait_for_load_state("networkidle")
        mc.get_by_text(SEL.MCMP["resultados_tab"], exact=True).first.click()
        mc.wait_for_load_state("networkidle")
        # Precondición: sin el panel de resultados no hay datos que leer.
        mc.get_by_text("Filtro Aplicado", exact=False).first.wait_for(
            state="visible", timeout=30000)
        self._verificar_filtro(mc, desde, hasta)
        self._mostrar_columnas(mc, columnas)
        return self._leer_todas_las_paginas(mc)

    def _abrir_mcmp(self) -> None:
        """Abre Mis Comprobantes desde el portal (misma sesión). Si expiró, lo
        detecta por la URL de login y lanza SesionExpirada."""
        if self._mcmp is not None and not self._mcmp.is_closed():
            return
        # Principal: buscador del portal. Alternativo: 'Ver todos' > Mis servicios.
        self._mcmp = primer_camino([self._mcmp_por_buscador, self._mcmp_por_mis_servicios])
        self._mcmp.wait_for_load_state("networkidle")
        if self._es_login(self._mcmp.url):
            raise SesionExpirada()
        self._mcmp_home = self._mcmp.url

    def _ir_al_portal(self) -> Page:
        portal = self._portal
        portal.goto(self._portal_url, wait_until="domcontentloaded")
        if self._es_login(portal.url):
            raise SesionExpirada()
        return portal

    def _abrir_en_pestana(self, portal: Page, elemento) -> Page:
        """Click que abre la app en pestaña nueva (o en la misma, si ARCA no la abre)."""
        try:
            with self._context.expect_page(timeout=8000) as pi:
                elemento.click()
            return pi.value
        except Exception:
            return portal

    def _mcmp_por_buscador(self) -> Page:
        portal = self._ir_al_portal()
        portal.locator(SEL.MCMP["buscador"]).fill("Mis Comprobantes")
        portal.wait_for_timeout(1500)
        link = portal.get_by_role("link", name=SEL.MCMP["mis_comprobantes"]).first
        link.wait_for(state="visible", timeout=10000)
        return self._abrir_en_pestana(portal, link)

    def _mcmp_por_mis_servicios(self) -> Page:
        portal = self._ir_al_portal()
        portal.get_by_role("link", name=SEL.MCMP["ver_todos"]).first.click()
        # Sin 'networkidle' (el portal no se queda quieto): se espera la tarjeta.
        tarjeta = portal.get_by_text(
            re.compile(SEL.MCMP["tarjeta_mis_comprobantes"], re.I)).first
        tarjeta.wait_for(state="visible", timeout=10000)
        return self._abrir_en_pestana(portal, tarjeta)

    def _filtrar(self, mc: Page, desde: str, hasta: str, tipos: list[str]) -> None:
        # Fecha: daterangepicker único; 'desde - hasta'. Tab cierra el calendario
        # sin tocar botones (no clickear a ciegas).
        fecha = mc.locator(SEL.MCMP["fecha"])
        fecha.fill(f"{desde} - {hasta}")
        fecha.dispatch_event("keyup")
        fecha.dispatch_event("change")
        fecha.press("Tab")
        # En Emitidos el 'CUIT del Emisor' es un <select> ya scopeado al
        # contribuyente (idContribuyente=0): no hay que tocarlo.
        self._elegir_tipos(mc, tipos)

    def _elegir_tipos(self, mc: Page, tipos: list[str]) -> None:
        """Tipo de comprobante: bootstrap-select MÚLTIPLE con buscador interno.
        Marca cada tipo por nombre EXACTO (sin coincidir con variantes como
        'Factura A con leyenda...'), y verifica que queden seleccionados."""
        mc.locator(SEL.MCMP["tipo_btn"]).click()
        for tipo in tipos:
            mc.locator(SEL.MCMP["tipo_search"]).first.fill(tipo)
            opcion = (mc.locator("ul.dropdown-menu li a span.text")
                      .filter(has_text=re.compile(rf"^\s*{re.escape(tipo)}\s*$"))
                      .first)
            opcion.wait_for(state="visible", timeout=5000)
            opcion.click()
        # Verificación: deben quedar exactamente los tipos pedidos marcados.
        seleccionados = mc.locator("ul.dropdown-menu li.selected a span.text").all_inner_texts()
        if sorted(s.strip() for s in seleccionados) != sorted(tipos):
            raise RuntimeError(
                f"Tipos marcados {seleccionados} != pedidos {tipos}. No leo la tabla.")
        # El desplegable tapa el botón Buscar: Escape NO lo cierra. Se cierra con
        # su propio botón (toggle) para que el click siguiente no caiga en la lista.
        if mc.locator("div.bootstrap-select.open").count():
            mc.locator(SEL.MCMP["tipo_btn"]).click()
            mc.wait_for_timeout(300)

    def _verificar_filtro(self, mc: Page, desde: str, hasta: str) -> None:
        # ARCA intercala espacios no separables (\xa0) en el panel (Emitidos):
        # se normaliza el whitespace antes de comparar.
        texto = re.sub(r"\s+", " ", mc.locator("body").inner_text().replace("\xa0", " "))
        ok = re.search(rf"Fecha del Comprobante:\s*{re.escape(desde)}\s*a\s*{re.escape(hasta)}", texto)
        if not ok or "Nro. de Comprobante:" in texto:
            i = texto.find("Fecha del Comprobante")
            visto = texto[i:i + 120] if i >= 0 else "(no aparece 'Fecha del Comprobante')"
            raise RuntimeError(
                f"El filtro aplicado no es {desde} a {hasta} (datos no confiables). "
                f"Panel visto: {visto!r}")

    def _mostrar_columnas(self, mc: Page, columnas: list[str]) -> None:
        mc.locator(SEL.MCMP["btn_columnas"]).click()
        for col in columnas:
            item = mc.locator(SEL.MCMP["col_item"]).filter(
                has_text=re.compile(rf"^\s*{re.escape(col)}\s*$"))
            if not item.count():
                continue
            if "active" not in (item.first.get_attribute("class") or "").split():
                item.first.click()  # solo si está oculta (clickear una activa la oculta)
        self._cerrar_menu(mc)

    def _cerrar_menu(self, mc: Page) -> None:
        fondo = mc.locator(SEL.MCMP["cerrar_menu"])
        if fondo.count() and fondo.first.is_visible():
            fondo.first.click()
            mc.wait_for_timeout(500)

    def _leer_todas_las_paginas(self, mc: Page) -> list[str]:
        total = self._total_registros(mc)
        if total > 5:
            self._mostrar_50(mc)
        paginas = [mc.content()]
        while True:
            # Sin tiempo: se corta para liberar el worker (el tipo queda como falla).
            if self._queda() <= 0:
                raise TimeoutError("Se agotó el plazo de la consulta leyendo páginas.")
            nxt = mc.locator(SEL.MCMP["next"])
            if not nxt.count() or "disabled" in (nxt.get_attribute("class") or "").split():
                break
            nxt.locator("a").click()
            mc.wait_for_timeout(800)
            paginas.append(mc.content())
        return paginas

    def _total_registros(self, mc: Page) -> int:
        m = re.search(r"de un total de\s*([\d.]+)", mc.locator(SEL.MCMP["info"]).inner_text())
        return int(m.group(1).replace(".", "")) if m else 0

    def _mostrar_50(self, mc: Page) -> None:
        mc.locator(SEL.MCMP["btn_page_length"]).click()
        opcion = (mc.locator(".dt-button-collection .dt-button")
                  .filter(has_text=re.compile(r"^\s*50\s*$")).first)
        opcion.wait_for(state="visible", timeout=5000)
        opcion.click()
        mc.wait_for_timeout(800)
        self._cerrar_menu(mc)

    # ------------------------------------------------------ RCEL (PDF de ventas)
    def descargar_pdfs_ventas(self, desde: str, hasta: str, excluir: set,
                              limite: int | None,
                              plazo: float | None = None) -> list[tuple[PdfRef, bytes]]:
        self._plazo = plazo
        return self._vigilado(lambda: self._descargar_pdfs_ventas(desde, hasta, excluir, limite))

    def _descargar_pdfs_ventas(self, desde: str, hasta: str, excluir: set,
                               limite: int | None) -> list[tuple[PdfRef, bytes]]:
        """RCEL > Consultas en [desde, hasta]; baja con la sesión autenticada el PDF
        ('Ver') de cada venta que no esté en `excluir`, hasta `limite`."""
        self._ensure()
        try:
            self._abrir_rcel()
            rc = self._rcel
            _first(rc, SEL.RCEL["menu_consultas"]).click()
            rc.wait_for_load_state("networkidle")
            _first(rc, SEL.RCEL["fecha_desde"]).fill(desde)
            _first(rc, SEL.RCEL["fecha_hasta"]).fill(hasta)
            _first(rc, SEL.RCEL["btn_buscar"]).click()
            rc.wait_for_load_state("networkidle")
            if self._es_login(rc.url):
                raise SesionExpirada()
            _first(rc, SEL.RCEL["tabla_resultados"], timeout=30000)
            refs = [r for r in parse_rcel_pdf_refs(rc.content()) if r.clave not in excluir]
            if limite is not None:
                refs = refs[:limite]
            out: list[tuple[PdfRef, bytes]] = []
            for ref in refs:
                # Corta 10 s antes del plazo para devolver a tiempo lo ya bajado y que
                # se guarde: la próxima consulta sigue con los que falten.
                if self._queda() <= MARGEN_PARA_GUARDAR_S:
                    break
                resp = self._context.request.get(urljoin(rc.url, ref.ver_path))
                body = resp.body()
                if not body.startswith(b"%PDF"):
                    raise RuntimeError(
                        f"RCEL no devolvió un PDF para {ref.clave} (HTTP {resp.status}).")
                out.append((ref, body))
            return out
        except SesionExpirada:
            raise
        except Exception:
            self._dump_fallo("rcel")
            raise

    def _abrir_rcel(self) -> None:
        """Abre Comprobantes en Línea desde el portal y elige la empresa. Reusa la
        pestaña si ya está abierta (vuelve al menú con la URL guardada)."""
        if self._rcel is not None and not self._rcel.is_closed():
            self._rcel.goto(self._rcel_menu, wait_until="domcontentloaded")
            if self._es_login(self._rcel.url):
                raise SesionExpirada()
            return
        portal = self._portal
        portal.goto(self._portal_url, wait_until="domcontentloaded")
        if self._es_login(portal.url):
            raise SesionExpirada()
        try:
            link = _first(portal, SEL.PORTAL["comprobantes_en_linea"], timeout=3000)
        except RuntimeError:
            portal.locator(SEL.MCMP["buscador"]).fill("Comprobantes en línea")
            portal.wait_for_timeout(1500)
            link = _first(portal, SEL.PORTAL["comprobantes_en_linea"], timeout=10000)
        try:
            with self._context.expect_page(timeout=8000) as pi:
                link.click()
            rc = pi.value
        except Exception:
            rc = portal
        rc.wait_for_load_state("networkidle")
        if self._es_login(rc.url):
            raise SesionExpirada()
        # Precondición: pantalla de selección de empresa.
        _first(rc, SEL.RCEL["empresa_marker"], timeout=15000)
        emp = rc.get_by_role("button", name=self.s.empresa, exact=False).first
        try:
            emp.wait_for(state="visible", timeout=8000)
        except Exception:
            emp = rc.locator(SEL.RCEL["empresa_btn"]).first
            emp.wait_for(state="visible", timeout=8000)
        emp.click()
        rc.wait_for_load_state("networkidle")
        self._rcel = rc
        self._rcel_menu = rc.url

    def _dump_fallo(self, paso: str) -> None:
        """Deja screenshot + HTML de la pantalla donde falló (no clickear a ciegas)."""
        pagina = self._rcel or self._portal
        if pagina is None or pagina.is_closed():
            return
        out = Path(__file__).resolve().parent.parent / "_spike_out"
        out.mkdir(exist_ok=True)
        try:
            pagina.screenshot(path=str(out / f"FALLO_{paso}.png"), full_page=True)
            (out / f"FALLO_{paso}.html").write_text(pagina.content(), encoding="utf-8")
        except Exception:  # noqa: BLE001 - el dump es best-effort
            pass

    @staticmethod
    def _es_login(url: str) -> bool:
        return "login" in (url or "") or "auth.afip" in (url or "")

    def relogin(self) -> None:
        self.close()
        self._ensure()

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        finally:
            self._pw = self._browser = self._context = None
            self._portal = self._mcmp = self._rcel = None
            self._portal_url = self._mcmp_home = self._rcel_menu = ""
