# Si Playwright queda colgado, se termina el proceso de la API

La API sync de Playwright solo se puede usar desde el hilo que la creó, así que un hilo del worker trabado no se puede cerrar desde otro hilo. Abrir una sesión nueva en paralelo arriesgaría dos sesiones de clave fiscal a la vez. Por eso, si un pedido sigue sin terminar pasado su plazo más un margen de 60 s, el worker termina el proceso (`os._exit(1)`), Railway lo reinicia y Chromium muere con él.

Cada acción de Playwright corta a los 30 s, así que esto solo ocurre ante un cuelgue real, no ante una consulta lenta. Requiere que el servicio `api` de Railway tenga activado el reinicio ante fallas.
