# Consulta a ARCA en segundo plano, con un plazo total de 4 minutos

La consulta completa (ventas, compras y PDFs) tardaba varios minutos dentro de una sola request HTTP, y un corte dun proxy hacía perder la respuesta aunque el backend ya hubiera guardado datos. Decidimos que `POST /sync/todo` responda 202 al instante y corra los tres tipos en segundo plano. Los clientes (un frontend o el cron) siguen el avance por tipo con `GET /sync/estado`, guardado en la tabla `sync_trabajo`. Toda la consulta comparte un solo plazo de 4 minutos: cada tipo usa el tiempo que queda, un tipo sin tiempo no se consulta, y los PDFs ya bajados se guardan antes del corte.

## Considered Options

- **Una request larga con un solo endpoint:** es la opción más simple, pero depende de los timeouts de los proxies intermedios y del borde de Railway.
- **Streaming de eventos de avance:** muestra el avance en vivo, pero también se pierde si se corta la conexión o se recarga la página.
- **Captura por tramos (tipo × quincena), retomando lo que falte:** se postergó, no se descartó. Hoy alcanza con PDFs incrementales y tipos que se reintentan enteros.

## Consequences

- Hay una sola consulta a la vez: si ya hay una en curso, `POST /sync/todo` responde 409.
- Si el backend se reinicia a mitad de una consulta, al arrancar la marca `interrumpido`.
- Se bajan como mucho 30 PDFs por consulta; la siguiente sigue con los que falten.
