// Diccionario en español: es la referencia. Las claves de `EN` salen de aquí (si falta una, no compila).
// Los marcadores `{nombre}` se sustituyen con `crearTraductor`.
export const ES = {
  // Cabecera y selector de idioma
  'cabecera.titulo': 'Observatorio de actividad sísmica',
  'cabecera.saltar': 'Saltar al contenido',
  'cabecera.replay': 'REPRODUCCIÓN: no son datos en directo · tiempos en UTC',
  'cabecera.directo': 'Eventos reales de USGS, tiempos en UTC',
  'selector.idioma': 'Idioma',

  // Pantalla de error de configuración
  'config.titulo': 'Configuración no válida',
  'config.ayuda_a': 'Edita',
  'config.ayuda_b': '(una sola clave,',
  'config.ayuda_c': ') y vuelve a compilar. Usa',
  'config.ayuda_d': 'como modelo: HTTPS de ngrok, o',
  'config.ayuda_e': 'solo en desarrollo.',
  'config.falta_url': 'Falta «apiBaseUrl» en config.json.',
  'config.url_invalida': '«apiBaseUrl» no es una URL válida.',
  'config.url_https': '«apiBaseUrl» debe usar HTTPS (http solo en localhost o 127.0.0.1).',
  'config.url_origen': '«apiBaseUrl» debe ser solo el origen de la API, sin ruta ni credenciales.',
  'config.url_marcador': '«apiBaseUrl» aún tiene el marcador SUBDOMINIO: pega la URL de ngrok.',
  'config.no_se_pudo_leer': 'No se pudo leer config.json.',
  'config.json_invalido': 'config.json no se pudo leer o no es un JSON válido.',

  // Valores de dominio que se muestran como etiqueta fija
  'dominio.sin_pais': 'Sin país asignado',
  'dominio.sin_pais_mar': 'Sin país asignado (mar o fuera de fronteras)',
  'dominio.sintetico': 'SINTÉTICO',
  'dominio.replay': 'REPRODUCCIÓN',

  // Formato y fechas
  'formato.nd': 'ND',
  'etiqueta.antiguos': 'datos del {hora}, desactualizados',
  'etiqueta.antiguos_nd': 'datos de {nd}, desactualizados',

  // Errores de la API (motivos legibles)
  'errores.red': 'La API no responde (red, túnel de ngrok caído o bloqueo CORS).',
  'errores.parametro': 'La API rechazó el parámetro «{parametro}».',
  'errores.parametro_generico': 'La API rechazó la consulta por un parámetro no válido.',
  'errores.servicio': 'Servicio no disponible: la base de datos no responde.',
  'errores.interno': 'Error interno de la API.',
  'errores.respuesta_invalida':
    'La API devolvió una respuesta que no es JSON (¿página de aviso de ngrok?).',
  'errores.http': 'La API respondió con el estado HTTP {status}.',
  'errores.metodo': 'El panel solo realiza peticiones GET.',
  'errores.configuracion': 'La configuración de la API no es válida.',
  'errores.desconocido': 'Error inesperado en el panel.',

  // Avisos del estado del sistema
  'avisos.api_sin_respuesta': 'La API no responde: se muestran los últimos datos recibidos.',
  'avisos.base_fallida': 'La base de datos no responde: las cifras no están disponibles.',
  'avisos.datos_desactualizados':
    'Los datos están desactualizados: la última ingesta de USGS es antigua.',

  // Estado del sistema
  'estado.aria': 'Estado del sistema',
  'estado.ultimo_acceso': 'Último acceso correcto a la API',
  'estado.ultima_ingesta': 'Última ingesta correcta de USGS',
  'estado.periodo': 'Periodo consultado',
  'estado.eventos_reales': 'Eventos reales',
  'estado.eventos_replay': 'Eventos en reproducción',
  'estado.comprobando': 'comprobando…',

  // Origen de los datos
  'vista.aria': 'Origen de los datos',
  'vista.leyenda': 'Datos',
  'vista.directo': 'En directo',
  'vista.replay': 'REPRODUCCIÓN',
  'vista.sinteticos': 'Incluir casos de prueba sintéticos',
  'vista.sinteticos_ayuda':
    'Apagado por defecto: así solo se ven eventos reales. La comparación histórica nunca los usa.',
  'vista.franja_replay':
    'Estos no son datos en directo: son eventos ya recibidos que se vuelven a publicar. «Ocurrencia» es el tiempo original; «Reproducido» es cuándo se reprodujeron. La comparación histórica solo existe en directo.',
  'vista.franja_sinteticos_a': 'Casos de prueba sintéticos incluidos:',
  'vista.franja_sinteticos_b': 'no son terremotos reales; llevan la marca «SINTÉTICO».',

  // Filtros
  'filtros.titulo': 'Filtros',
  'filtros.intro':
    'Mapa, tabla, recuentos y distribuciones usan todos los filtros. La comparación histórica solo usa magnitud y país o subregión.',
  'filtros.desde': 'Desde (UTC)',
  'filtros.desde_ayuda': 'Fecha y hora en UTC, no en hora local.',
  'filtros.hasta': 'Hasta (UTC)',
  'filtros.hasta_ayuda': 'Debe ser posterior a «Desde».',
  'filtros.magnitud_min': 'Magnitud mínima',
  'filtros.magnitud_min_ayuda': 'Entre −10 y 10, p. ej. 4,5.',
  'filtros.magnitud_max': 'Magnitud máxima',
  'filtros.magnitud_max_ayuda': 'No menor que la mínima.',
  'filtros.pais': 'País',
  'filtros.todos_paises': 'Todos los países',
  'filtros.cargando_paises': 'Cargando países…',
  'filtros.pais_ayuda': 'País según el polígono de sus coordenadas.',
  'filtros.subregion': 'Subregión',
  'filtros.todas_subregiones': 'Todas las subregiones',
  'filtros.subregion_ayuda': 'Se combina con el país (Y).',
  'filtros.error': 'Error: {mensaje}',
  'filtros.opciones_error': 'No se pudieron cargar las opciones de país o subregión ({motivo}).',
  'filtros.hora_acotada': 'El recuento por hora admite como máximo 31 días: se muestra {ventana}.',
  'filtros.aplicar': 'Aplicar',
  'filtros.restablecer': 'Restablecer',
  'filtros.estado_errores':
    'Corrige los errores para aplicar los filtros; mientras tanto se mantienen los anteriores.',
  'filtros.estado_pendiente':
    'Cambios pendientes: se aplican solos tras una breve pausa o con «Aplicar».',
  'filtros.estado_aplicados': 'Filtros aplicados.',
  'filtros.err_fecha': 'Fecha no válida (UTC, formato AAAA-MM-DDThh:mm).',
  'filtros.err_fecha_orden': 'La fecha final debe ser posterior a la inicial.',
  'filtros.err_magnitud': 'Introduce un número entre −10 y 10.',
  'filtros.err_magnitud_orden': 'La magnitud máxima no puede ser menor que la mínima.',
  'filtros.err_pais': 'Código de país no válido (tres letras mayúsculas).',
  'filtros.err_subregion': 'Máximo 80 caracteres.',
  'filtros.origen_sinteticos': 'Se incluyen casos de prueba sintéticos, marcados como «SINTÉTICO».',
  'filtros.origen_replay':
    'Datos de REPRODUCCIÓN: eventos ya recibidos que se vuelven a publicar; no son datos en directo.',
  'filtros.origen_reales': 'Solo se muestran eventos reales.',
  'filtros.cerrar': 'Cerrar filtros',
  'filtros.dialogo_aria': 'Filtros del panel',

  // Frase de filtros y superficies (010)
  'frase.aria': 'Filtros activos; cada trozo abre el formulario',
  'frase.todos_paises': 'todos los países',
  'frase.todas_magnitudes': 'todas las magnitudes',
  'frase.todo_periodo': 'todo el periodo',
  'frase.mag_min': '≥ {valor}',
  'frase.mag_max': '≤ {valor}',
  'frase.mag_rango': '{min}–{max}',
  'superficie.aria': 'Qué se muestra',
  'superficie.mapa': 'Mapa',
  'superficie.tabla': 'Tabla',
  'superficie.analisis': 'Análisis',

  // Mapa
  'mapa.titulo': 'Mapa de eventos',
  'mapa.tipo_aria': 'Tipo de mapa',
  'mapa.plano': 'Plano',
  'mapa.globo': 'Globo 3D',
  'mapa.usa_filtros': 'Usa todos los filtros.',
  'mapa.replay_nota': 'REPRODUCCIÓN: eventos reproducidos, no en directo.',
  'mapa.dibujados': '{n} eventos dibujados.',
  'mapa.truncado':
    'Aviso: el mapa muestra {devueltos} de {total} eventos (límite de la API). La tabla y los recuentos incluyen todos; acota los filtros para ver el resto.',
  'mapa.error_antiguo': 'No se pudo actualizar el mapa ({motivo}). Se muestran {datos}.',
  'mapa.error_carga': 'No se pudo cargar el mapa ({motivo}).',
  'mapa.seleccion_fuera':
    'El evento seleccionado no está entre los dibujados en el mapa; consúltalo en la tabla.',
  'mapa.error_fronteras':
    'No se pudieron cargar las fronteras de los países; el mapa sigue con los eventos.',
  'mapa.lienzo_aria': 'Mapa de eventos sísmicos',
  'mapa.descripcion':
    'Mapa interactivo: cada evento es un círculo; su tamaño indica la magnitud y su color la profundidad. Con el mapa enfocado, las flechas lo desplazan y + y − cambian el zoom. La tabla de eventos es la alternativa por teclado: el botón «Ver en el mapa» abre la ficha del evento.',
  'mapa.cargando': 'Cargando eventos…',
  'mapa.leyenda_resumen': 'Cómo leer el mapa',
  'mapa.leyenda_radio': 'Círculo más grande, magnitud mayor',
  'mapa.leyenda_color': 'Color: profundidad en km',
  'mapa.leyenda_escala_aria': 'Escala de profundidad',
  'mapa.superficie': 'superficie',
  'mapa.mas_profundo': 'más profundo',
  'mapa.leyenda_nd': 'Gris con borde discontinuo: sin dato (ND)',
  'mapa.leyenda_sintetico': 'SINTÉTICO: contorno grueso discontinuo',
  'mapa.pista': 'Pasa el ratón por un círculo para ver la magnitud; púlsalo para ver la ficha.',
  'mapa.no_disponible': 'Mapa no disponible en este entorno. Los eventos están en la tabla.',
  'mapa.anuncio': 'Evento {id} seleccionado; ficha abierta en el mapa.',
  'mapa.acercar': 'Acercar',
  'mapa.alejar': 'Alejar',
  'mapa.cerrar_ficha': 'Cerrar ficha',
  'mapa.fuente_fronteras': 'Fronteras: Natural Earth',
  'globo.leyenda_altura': 'Columna más alta, magnitud mayor',

  // Ficha y resumen del evento
  'ficha.aria_real': 'Ficha del terremoto {id}',
  'ficha.aria_sintetico': 'Ficha del caso de prueba sintético {id}',
  'ficha.titulo': 'Magnitud {magnitud}',
  'ficha.ocurrencia': 'Ocurrencia',
  'ficha.profundidad': 'Profundidad',
  'ficha.actualizado': 'Actualizado',
  'ficha.reproducido': 'Reproducido',
  'ficha.id': 'Identificador USGS',
  'ficha.resumen_sin_pais': 'sin país asignado',

  // Globo 3D
  'globo.aria':
    'Globo 3D con los eventos del filtro. El tamaño y la altura marcan la magnitud; el color del cuerpo, la profundidad, como en el mapa plano. Los pulsos rojos marcan los 60 terremotos más recientes. Arrastra para girar, rueda para acercar, pulsa un punto para seleccionarlo o un país para filtrarlo. La tabla de eventos es la alternativa accesible.',
  'globo.cargando': 'Cargando el globo…',
  'globo.sin_webgl':
    'Este navegador no puede dibujar el globo 3D (necesita WebGL). Usa la vista «Plano».',
  'globo.inactivo': 'Globo 3D no disponible en este entorno.',
  'globo.m2': 'M 2',
  'globo.m5': 'M 5',
  'globo.m7': 'M 7',
  'cinta.aria': 'Recorte local de las últimas 24 horas; no consulta la API',
  'cinta.etiqueta': 'Hasta',

  // Identidad (011): tema
  'tema.boton': 'Modo noche',
  'estado.corto_api': 'API',
  'estado.corto_usgs': 'USGS',
  'estado.corto_periodo': 'Periodo',
  'estado.corto_eventos': 'Eventos',
  'estado.corto_replay': 'Reproducidos',
  'tema.papel': 'Papel',
  'tema.noche': 'Noche',
  'escena.cifra_vs': '{hoy} frente a {media}',
  'escena.cifra_rotulo': 'hoy / media 2025',
  'escena.cifra_aviso': 'El último periodo puede estar incompleto.',
  'escena.grafica': 'Gráfica de la escena',
  'escena.serie_hora': 'Hora',
  'escena.serie_magnitud': 'Magnitud',
  'escena.serie_profundidad': 'Profundidad',

  // Tabla de eventos
  'tabla.titulo': 'Eventos',
  'tabla.nota': 'Usa todos los filtros. Orden: el de la API (más recientes primero).',
  'tabla.error_actualizar': 'No se pudo actualizar la tabla ({motivo}).',
  'tabla.se_muestran': 'Se muestran {datos}.',
  'tabla.vacio': 'Ningún evento cumple los filtros.',
  'tabla.resumen':
    '{total} eventos con los filtros aplicados; mostrando del {primero} al {ultimo}. Tiempos en UTC.',
  'tabla.col_ocurrencia': 'Ocurrencia (UTC)',
  'tabla.col_ocurrencia_original': 'Ocurrencia original (UTC)',
  'tabla.col_magnitud': 'Magnitud',
  'tabla.col_profundidad': 'Profundidad',
  'tabla.col_pais': 'País',
  'tabla.col_subregion': 'Subregión',
  'tabla.col_actualizado': 'Actualizado (UTC)',
  'tabla.col_reproducido': 'Reproducido (UTC)',
  'tabla.col_id': 'Identificador',
  'tabla.col_mapa': 'Mapa',
  'tabla.ver_aria': 'Ver en el mapa el evento {id}',
  'tabla.ver': 'Ver en el mapa',
  'tabla.seleccionado': 'Seleccionado',
  'tabla.paginacion_aria': 'Paginación de la tabla de eventos',
  'tabla.anterior': 'Anterior',
  'tabla.siguiente': 'Siguiente',
  'tabla.pagina': 'Página {pagina} de {paginas}',
  'tabla.cargando': 'Cargando eventos…',
  'tabla.sin_datos': 'No hay datos de la tabla todavía.',

  // Comparación histórica
  'comparacion.titulo': 'Comparación histórica',
  'comparacion.nota_replay': 'Solo existe en directo',
  'comparacion.nota_directo': 'Solo usa magnitud y país/subregión; ignora las fechas',
  'comparacion.solo_directo':
    'La comparación histórica solo existe en directo. En REPRODUCCIÓN no se calcula: las cifras de reproducción no se pueden comparar con la media diaria de 2025. Vuelve a «En directo» para verla.',
  'comparacion.ultimas_24h': 'Últimas 24 h',
  'comparacion.eventos_ventana': 'eventos · {desde} a {hasta}',
  'comparacion.media': 'Media diaria de 2025',
  'comparacion.no_cargado': 'el histórico de 2025 no está cargado',
  'comparacion.eventos_dias': '{eventos} eventos en {dias} días',
  'comparacion.cociente': 'Cociente (24 h ÷ media 2025)',
  'comparacion.cociente_ayuda': '1 = igual que la media diaria',
  'comparacion.v_debajo': '{pct} % por debajo de la media diaria',
  'comparacion.v_encima': '{pct} % por encima de la media diaria',
  'comparacion.v_igual': 'Igual que la media diaria',
  'comparacion.filtro_efectivo': 'Filtro efectivo:',
  'comparacion.no_disponible_ahora': 'Comparación no disponible por ahora.',
  'comparacion.aviso':
    'El último periodo puede estar incompleto: USGS publica con retraso y revisa los eventos después.',
  'comparacion.no_disponible': 'no disponible',
  'comparacion.f_sin_limites': 'magnitud: sin límites',
  'comparacion.f_min': 'magnitud ≥ {valor}',
  'comparacion.f_max': 'magnitud ≤ {valor}',
  'comparacion.f_y': 'y',
  'comparacion.f_completo': '{magnitud} · país: {pais} · subregión: {subregion}',
  'comparacion.f_todos': 'todos',
  'comparacion.f_todas': 'todas',

  // Bloques compartidos por recuentos y distribuciones
  'bloque.estado_actual': 'Estado actual de cada evento, con todos los filtros activos',
  'bloque.sin_eventos': 'No hay eventos que cumplan los filtros actuales.',

  // Recuentos
  'recuentos.titulo': 'Recuentos',
  'recuentos.grupo_pais': 'Eventos por país',
  'recuentos.grupo_subregion': 'Eventos por subregión',
  'recuentos.agrupar': 'Agrupar por',
  'recuentos.total': 'Total',
  'recuentos.repartidos': 'Repartidos en',
  'recuentos.eventos': 'eventos',
  'recuentos.n_paises': 'países',
  'recuentos.n_subregiones': 'subregiones',
  'recuentos.mayor': 'Mayor',
  'recuentos.pico': 'Hora con más eventos',
  'recuentos.media_hora': 'Media por hora',
  'recuentos.media_ref': 'media {valor}',
  'recuentos.eje_eventos': 'Eventos (recuento)',
  'recuentos.resto_nota':
    'El gráfico muestra las {n} mayores categorías y agrupa el resto; la tabla incluye todas.',
  'recuentos.hora_titulo': 'Eventos por hora (UTC)',
  'recuentos.hora_acotada':
    'El rango pedido supera 31 días: se muestran los 31 días hasta {hasta}.',
  'recuentos.hora_sin_fechas':
    'Sin fechas en los filtros, este gráfico muestra las últimas 24 h; los demás bloques usan todo el periodo disponible.',
  'recuentos.hora_sin_fechas_replay':
    'Sin fechas en los filtros, este gráfico muestra las últimas 24 h hasta el último evento reproducido; los demás bloques usan todo el periodo disponible.',
  'recuentos.sin_ventanas': 'No hay ventanas horarias para el periodo consultado.',
  'recuentos.ventanas': '{n} ventanas de 1 h, {ceros} sin eventos.',
  'recuentos.eje_hora': 'Hora UTC (inicio de cada ventana de 1 h, no hora local)',

  // Distribuciones
  'distribuciones.titulo': 'Distribuciones',
  'distribuciones.magnitud': 'Magnitud',
  'distribuciones.profundidad': 'Profundidad',
  'distribuciones.nota_a': '{n} eventos; de ellos',
  'distribuciones.sin_magnitud': 'sin magnitud registrada (no cuentan como 0).',
  'distribuciones.sin_profundidad': 'sin profundidad registrada (no cuentan como 0).',
  'distribuciones.grafico_magnitud': 'Distribución de la magnitud',
  'distribuciones.grafico_profundidad': 'Distribución de la profundidad',
  'distribuciones.eje_magnitud': 'Magnitud (intervalos)',
  'distribuciones.eje_profundidad': 'Profundidad (km, intervalos; el color es el del mapa)',
  'distribuciones.eventos': 'Eventos',
  'distribuciones.moda': 'Intervalo más frecuente',

  // Gráfico de barras
  'grafico.eventos': 'eventos',
  'grafico.sin_valor': 'Sin valor',
  'grafico.resto': 'Resto',
  'grafico.leyenda_aria': 'Cómo leer las barras',
  'grafico.leyenda_cero': 'Línea con borde: 0, sin eventos',
  'grafico.leyenda_sin_valor': 'Rayada: eventos sin valor (no son 0)',
  'grafico.leyenda_nd': 'valor desconocido',
  'grafico.ver_tabla': 'Ver «{titulo}» como tabla',
  'grafico.col_categoria': 'Categoría',
  'grafico.col_observacion': 'Observación',
  'grafico.obs_cero': 'Sin eventos (0)',
  'grafico.obs_sin_valor': 'Eventos sin valor registrado (no cuentan como 0)',
  'grafico.obs_nd': 'Valor desconocido (ND)',
  'grafico.alt_vacio': '{titulo}. Sin categorías que mostrar.',
  'grafico.alt_resumen': '{n} categorías, {total} {unidad} en total.',
  'grafico.alt_mayor': 'Mayor: {etiqueta}, {valor}.',
  'grafico.alt_ceros': '{n} categorías con 0.',
  'grafico.alt_sin_valor': 'Sin valor: {valor}.',
  'grafico.alt_nd': '{n} categorías con valor desconocido (ND).',
  'grafico.alt_tabla': 'La tabla equivalente está debajo del gráfico.',

  // Carga y error de un bloque
  'aviso.cargando': 'Cargando datos…',
  'aviso.error': 'No se pudieron cargar los datos: {motivo}',
  'aviso.antiguos':
    'Datos desactualizados: no se pudo actualizar ({motivo}). Se muestra la última lectura correcta, de las {hora}.',

  // Nota sobre el alcance de las cifras
  'nota.aria': 'Límite de las cifras',
  'nota.texto':
    'Estas cifras describen lo que USGS ha publicado en el periodo filtrado. No predicen terremotos ni evalúan el riesgo. La red no detecta todos los eventos por igual y el tipo de magnitud puede cambiar de un evento a otro: compara solo muestras con los mismos filtros.',
} as const;

export type Clave = keyof typeof ES;
