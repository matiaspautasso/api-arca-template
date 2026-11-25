"""Selectores de ARCA / RCEL — PUNTO ÚNICO DE VERDAD de producción (verificados).

Resiliencia: selectores semánticos (rol/texto/label) con varios candidatos por
elemento; se prueban en orden (ver find_first() en rcel_client.py). Si ARCA
cambia la UI, se corrige ACÁ.

Spec: {"by": "css"|"role"|"label"|"text"|"placeholder", ...} (ver build_locator).
"""

LOGIN = {
    "cuit_input": [
        {"by": "css", "value": "#F1\\:username"},
        {"by": "label", "text": "CUIT"},
    ],
    "btn_siguiente": [
        {"by": "css", "value": "#F1\\:btnSiguiente"},
        {"by": "role", "role": "button", "name": "Siguiente"},
    ],
    "password_input": [
        {"by": "css", "value": "#F1\\:password"},
        {"by": "label", "text": "Clave"},
    ],
    "btn_ingresar": [
        {"by": "css", "value": "#F1\\:btnIngresar"},
        {"by": "role", "role": "button", "name": "Ingresar"},
    ],
}

# ----------------------------------------------------- MIS COMPROBANTES (MCMP)
# App fes.afip.gob.ar/mcmp (misma sesión de clave fiscal, SSO). Ventas = Emitidos,
# compras = Recibidos. DataTable sin atributos title -> se mapea por encabezado.
# Selectores verificados contra el DOM real.
MCMP = {
    "buscador": "#buscadorInput",                         # buscador del portal
    "mis_comprobantes": "Mis Comprobantes",               # link del resultado
    # Camino alternativo (verificado 2026-11-20): Inicio > 'Ver todos' (Más utilizados)
    # -> /portal/app/mis-servicios, tarjeta <h3>MIS COMPROBANTES</h3> (no es link).
    "ver_todos": "Ver todos",
    "tarjeta_mis_comprobantes": r"^\s*mis comprobantes\s*$",  # regex, sin mayúsculas
    "emitidos": "Emitidos",                               # sección ventas
    "recibidos": "Recibidos",                             # sección compras
    "fecha": "#fechaEmision",                             # daterangepicker 'desde - hasta'
    "tipo_btn": 'button[data-id="tipoComprobante"]',      # bootstrap-select
    "tipo_search": ".bs-searchbox input",                 # buscador interno del select
    "buscar": "Buscar",
    "resultados_tab": "Resultados",
    "btn_columnas": 'button[title="Mostrar/ocultar columnas"]',
    "col_item": "li.buttons-columnVisibility",            # toggle (class 'active' = visible)
    "cerrar_menu": "div.dt-button-background",            # fondo del menú (Escape no cierra)
    "btn_page_length": 'button[title="Cantidad de registros por página"]',
    "tabla": "table#tablaDataTables",
    "info": "#tablaDataTables_info",                      # 'Mostrando ... de un total de N'
    "next": "li#tablaDataTables_next",
    # VENTAS (Emitidos): sin filtro de tipo; columnas de receptor + IVA por alícuota.
    "cols_ventas": ["Doc. Receptor", "Denominación Receptor",
                    "IVA 10,5%", "IVA 21%", "Neto Grav. IVA 21%",
                    "IVA 27%", "Neto Grav. IVA 27%", "Neto Gravado Total",
                    "Imp. Total"],
    # Tipos a filtrar (nombres EXACTOS del desplegable de ARCA, verificados).
    "tipos_ventas": ["Factura A", "Factura B", "Nota de Crédito A"],
    "tipos_compras": ["Factura A", "Factura B", "Factura C",
                      "Recibo B", "Nota de Crédito A"],
    # COMPRAS (Recibidos): columnas de emisor + IVA.
    "cols_compras": ["CUIT Emisor", "IVA 10,5%", "IVA 21%", "Neto Grav. IVA 21%",
                     "IVA 27%", "Neto Grav. IVA 27%", "Imp. Total"],
}

# --------------------------------------------- RCEL (Comprobantes en Línea) — PDFs
# Solo para bajar el PDF de las ventas ("Ver" -> imprimirComprobante.do?c=<id>).
# Verificados en el spike (spike_rcel.py, 2026-11-03).
PORTAL = {
    "comprobantes_en_linea": [
        {"by": "role", "role": "link", "name": "Comprobantes en línea"},
        {"by": "text", "text": "Comprobantes en línea"},
    ],
}

RCEL = {
    "empresa_marker": [
        {"by": "text", "text": "Seleccione la Empresa a representar"},
        {"by": "text", "text": "Representado"},
    ],
    "empresa_btn": "input.btn_empresa",                   # value = nombre de la empresa
    "menu_consultas": [
        {"by": "role", "role": "link", "name": "Consultas"},
        {"by": "role", "role": "button", "name": "Consultas"},
        {"by": "text", "text": "Consultas"},
    ],
    "fecha_desde": [
        {"by": "label", "text": "Desde"},
        {"by": "placeholder", "text": "dd/mm/aaaa"},
    ],
    "fecha_hasta": [
        {"by": "label", "text": "Hasta"},
    ],
    "btn_buscar": [
        {"by": "role", "role": "button", "name": "Buscar"},
        {"by": "css", "value": "#btnBuscar"},
    ],
    "tabla_resultados": [
        {"by": "css", "value": "table:has(th:has-text('Importe Total'))"},
    ],
}
