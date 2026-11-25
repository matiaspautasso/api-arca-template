# Sin `networkidle` en el portal de ARCA

Desde Railway, el portal de clave fiscal (`portalcf.cloud.afip.gob.ar`) nunca deja de hacer pedidos de red. Por eso `wait_for_load_state("networkidle")` cortaba a los 30 s logins que ya habían entrado bien (2026-11-20). Desde una máquina local el portal sí se queda quieto, así que el problema no se reproduce fuera de producción. En el portal se espera el elemento que confirma la pantalla: el buscador `#buscadorInput` después del login, o la tarjeta "MIS COMPROBANTES" en Mis servicios. No hay que volver a agregar esa espera.
