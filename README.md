# Sistema de Control de Asistencia y Novedades Laborales

Prototipo académico local de escritorio para organizar registros de
asistencia y administrar información de permisos y horas extra en una pequeña
empresa del sector de la construcción.

## Objetivo general

Desarrollar un prototipo local que facilite la organización, consulta y revisión
de registros de asistencia y novedades laborales, mediante reglas informativas
de validación y almacenamiento estructurado.

## Alcance y limitaciones

- Gestiona códigos internos y datos laborales mínimos de empleados.
- Permite registrar y consultar marcaciones; identifica campos faltantes,
  fechas u horas no reconocidas, posibles duplicados y códigos sin empleado.
- Importa CSV o Excel `.xlsx` mediante mapeo de columnas, vista previa y
  confirmación; permite elegir la hoja cuando el Excel tiene varias. Identifica
  faltantes, formatos no reconocidos,
  duplicados y empleados sin asociación; no completa ni corrige valores.
- Conserva por lote una etiqueta genérica de archivo, la huella SHA-256, el
  mapeo permitido y la clasificación declarada de la fuente; no guarda el nombre
  local del archivo. En cada fila conserva solo los valores originales
  mapeados de código interno, fecha y horas; excluye encabezados de nombres,
  identificadores, datos de contacto y salario. Los reportes agrupados usan
  etiquetas genéricas y permiten asignar cada bloque a un código interno.
- Permite registrar y actualizar solicitudes de permisos con tipo, motivo,
  fechas/horas, duración informada en horas y días, clasificación remunerado/no
  remunerado, estado, observaciones e indicadores de firma/Vo. Bo. registrados.
- Permite registrar horas extra reportadas, periodo, día, horas totales y extra,
  jornada, actividad, trabajo en hora de almuerzo, dato de domingos/festivos,
  recargo informado, autorización y aprobación, sin calcular pagos ni
  liquidaciones oficiales.
- Ofrece filtros de consulta, resumen de integridad informativo y exportación a
  CSV o Excel.
- Las alertas no determinan ausencias injustificadas, fraude, incumplimientos
  ni errores de nómina. Los registros originales no se modifican por alertas.
- No calcula salarios, recargos, prestaciones, seguridad social, impuestos ni
  nómina electrónica. No procesa biometría ni se conecta con equipos,
  plataformas externas o DIAN.
- La aplicación es local y no incorpora autenticación ni una política de
  respaldos automática. La base y los informes deben guardarse en ubicaciones
  autorizadas y protegidas. No se debe cargar información real en el repositorio.
- El nivel TRL no se declara certificado: requiere validar el prototipo en un
  entorno pertinente y con evidencia autorizada.

## Tecnologías

- Python 3.11 o posterior con Tkinter disponible.
- Tkinter para la interfaz de escritorio y SQLite (biblioteca estándar de Python).
- `openpyxl` para exportar informes `.xlsx`.
- `pytest` para las pruebas automatizadas.
- Git para control de versiones.

No se requiere Pandas. La importación CSV y los informes CSV usan la biblioteca
estándar `csv`.

## Aplicación principal: Tkinter

La aplicación de escritorio Tkinter es la única interfaz del proyecto. Su punto
de entrada es `main.py` y utiliza `data/asistencia_laboral.db` de manera
predeterminada. No requiere servidor web ni navegador. Para las pruebas se puede
seleccionar otra base mediante `NEXORA_HR_DB_PATH`; el valor `:memory:` crea
una base SQLite temporal en memoria.

Para ejecutarla en Windows con Python 3.11 o posterior y Tkinter:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

La aplicación no inicia un servicio HTTP. Mantiene la base local separada de
cualquier base de demostración anterior; no se migran ni combinan registros.
Las funciones de importación, validación, reportes y persistencia se ejecutan
mediante los servicios Python y SQLite compartidos.

## Interfaz y experiencia de usuario

La aplicación organiza sus módulos mediante una navegación lateral desplazable
y una zona de trabajo de escritorio. Los colores, botones y paneles usan estilos
locales; los botones, iconos, tarjetas y navegación mantienen colores y
geometría estables al pasar el puntero. El logotipo recupera el monograma N
anterior con barras ascendentes y acentos índigo/teal. El panel usa una
ilustración vectorial dibujada en Tkinter y tarjetas con jerarquía tipográfica
reforzada. La interfaz prefiere Inter o Aptos si están instaladas, después
Segoe UI Variable y Segoe UI. No hay animaciones de botón, transición,
contadores escalonados ni barras de progreso animadas; la lectura de archivos
de importación se mantiene en segundo plano y muestra un estado de texto
estático.

El panel muestra indicadores de empleados, marcaciones, permisos pendientes,
horas extra y alertas informativas, además de actividad de asistencia reciente.
Los módulos de asistencia, permisos, horas extra e informes ofrecen tablas,
formularios y acciones de confirmación. Las alertas no determinan faltas ni
liquidaciones oficiales; las acciones de eliminación son explícitas.

## Estructura

```text
SistemaControlAsistencia/
├── main.py
├── database/
│   ├── __init__.py
│   └── connection.py
├── modules/
│   ├── asistencia.py
│   ├── empleados.py
│   ├── horas_extras.py
│   ├── permisos.py
│   ├── reportes.py
│   └── validaciones.py
├── views/
│   ├── estilos.py
│   └── ventana_principal.py
├── tests/
│   ├── fixtures/
│   │   └── datos_ficticios_proyecto.json
│   ├── test_main.py
│   └── test_system.py
├── data/                 # La base local se crea al iniciar
├── requirements.txt
├── README.md
└── .gitignore
```

La carpeta `data/` y la base SQLite se crean al iniciar la aplicación por
primera vez.

## Tamaño de ventana y navegación

El menú lateral se adapta a la altura disponible y permite desplazarse cuando
no caben todas las opciones. El área de trabajo también tiene desplazamiento
vertical: la rueda del ratón desplaza la página y, al pasar sobre una tabla,
desplaza sus filas. Las tablas muestran barras vertical y horizontal; `Shift`
con la rueda permite recorrer columnas anchas. Los accesos rápidos del panel
tienen una fila propia y no se ocultan ni cambian de posición con el ancho. En
Asistencia y en Informes, los botones de acción se ubican en una fila separada
de los filtros para evitar que se corten en ventanas angostas. En Empleados,
las acciones sobre la selección también tienen su propia fila.

## Módulos funcionales

1. **Empleados:** alta, consulta, edición, búsqueda por código/nombre y
   activación o desactivación; los selectores muestran código y nombre en una
   lista desplazable. Permite eliminar empleados solo cuando no tienen
   asistencia, permisos ni horas extra asociados.
2. **Asistencia:** captura manual, importación CSV/Excel autorizada, filtros
   por empleado y periodo, alertas, consulta, eliminación confirmada de una
   marcación individual y exportación CSV.
3. **Permisos:** alta, consulta, edición de fechas, tipo, clasificación,
   duración reportada, observaciones, estado e indicadores de firma/Vo. Bo.;
   permite eliminar solicitudes seleccionadas con confirmación.
4. **Horas extra:** alta, consulta y edición de empleado, periodo, día,
   horarios, total y horas extra, jornada, actividad, almuerzo, autorización y
   aprobación; permite eliminar registros seleccionados con confirmación.
5. **Validaciones:** identificación no destructiva de faltantes, fechas y horas
   no válidas, registros repetidos y salida anterior a entrada.
6. **Consultas e informes:** búsqueda por módulo, empleado y periodo; resumen
   local; exportación de resultados CSV o Excel.

Los empleados se pueden eliminar permanentemente solo si no tienen marcaciones,
permisos ni horas extra asociados. Para conservar la integridad y trazabilidad,
los empleados con historial se deben desactivar en lugar de eliminar. Las
eliminaciones individuales de marcaciones, permisos y horas extra requieren
confirmación y no se pueden deshacer; la información eliminada no se recupera
desde la aplicación.

### Importación y revisión de asistencia

Al seleccionar un CSV o Excel `.xlsx`, la página de Asistencia permite
seleccionar hoja cuando hay varias y relacionar las columnas con código
interno, fecha, entrada y salida. Los encabezados frecuentes se sugieren automáticamente; la persona que
opera debe revisar la vista previa y confirmar explícitamente. Las celdas vacías
se mantienen vacías. Registros con alertas y posibles duplicados no se
descartan ni se corrigen automáticamente.

```csv
codigo_trabajador,fecha,entrada,salida
DEMO-001,2026-10-25,08:00,17:00
```

Los códigos desconocidos se conservan sin asociación y generan una alerta. Las
fechas `AAAA-MM-DD`, `AAAA/MM/DD` y `DD/MM/AAAA`, y las horas `HH:MM`,
`HH:MM:SS`, AM/PM o fecha-hora reconocida se normalizan para consulta. La
trazabilidad conserva solo los valores originales de las columnas mapeadas
(código interno, fecha y horas), el lote y la fila de origen; no guarda la fila
completa ni el nombre local del archivo. Las columnas con encabezados de nombres,
identificadores, datos de contacto o salario se excluyen de la vista previa y
del almacenamiento; también se bloquea su mapeo manual. La fuente de cada fila
se registra como categoría controlada (por ejemplo, "Datos sintéticos"). En
reportes agrupados,
cada bloque recibe una etiqueta genérica y se puede asociar manualmente a un
código interno. El archivo original no se modifica ni se copia al repositorio.

### Fuentes documentales y trazabilidad académica

Las fuentes documentales del proyecto se mantienen fuera del repositorio y de
las bases de datos del prototipo. Las plantillas F-012 y F-074 orientan los
campos de los módulos de permisos y horas extra; los reportes de asistencia se
usan solo para orientar el mapeo de campos. No se incluyen nombres de archivos
locales, filas reales ni documentos privados en el repositorio. La suite usa
únicamente códigos, personas, horarios y operaciones ficticios.

La trazabilidad funcional se respalda en pruebas automatizadas de asistencia,
importación sintética y minimizada, permisos, horas extra, validaciones,
persistencia, exportaciones y separación de bases. Ninguna de estas pruebas
demuestra validación con trabajadores ni en el entorno de la empresa.

`main.py` usa `data/asistencia_laboral.db` de manera predeterminada. Puede
seleccionarse una base temporal estableciendo `NEXORA_HR_DB_PATH` antes de
iniciar el programa. Las bases locales preexistentes no se migran ni se borran
al cambiar la interfaz.

La suite usa una base temporal y el conjunto separado
`tests/fixtures/datos_ficticios_proyecto.json`, identificado expresamente como
sintético. No se usa la base de trabajo local como fixture ni se cargan fuentes
laborales al entorno de pruebas.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Instala `requirements.txt` antes de ejecutar la suite. Las pruebas usan bases
de datos temporales y registros ficticios. La ejecución local más reciente de
`python -m pytest -q` finalizó con **79 aprobadas, 0 fallidas y 0 omitidas**.
Los resultados son pruebas automatizadas; no equivalen a validación manual con
usuarios ni a las ejecuciones realizadas en otros entornos.
Los casos representativos y sus resultados incluyen:

| Caso | Entrada sintética | Resultado esperado y observado |
|---|---|---|
| CP-01 | Asistencia con código ficticio, fecha y entrada/salida válidas | Se guarda y se puede consultar; aprobado. |
| CP-02 | Marcación sin hora de entrada o de salida | Se genera una alerta sin completar ni modificar el campo; aprobado. |
| CP-03 | Fecha u hora no reconocida, o salida anterior a entrada | Se informa que el dato requiere revisión; no se infiere su causa ni se corrige; aprobado. |
| CP-04 | Dos marcaciones ficticias coincidentes | Ambas quedan señaladas como posible duplicado y se conservan; aprobado. |
| CP-05 | Solicitud de permiso ficticia en estado pendiente | Se guarda y se muestra para revisión, sin dar por registrada una aprobación; aprobado. |
| CP-06 | Hora extra ficticia sin autorización registrada | Se genera una alerta; no se calcula recargo ni pago; aprobado. |
| CP-07 | Exportación de registros y observaciones sintéticas | Se conserva el resultado de consulta en CSV/Excel; aprobado. |
| CP-08 | Entrada sintética 22:00 y salida 06:00 | Se conserva la fecha y las horas; se advierte el posible cruce de medianoche y la clasificación derivada muestra 00:00 diurnas y 08:00 nocturnas. La persona responsable debe confirmar la interpretación operativa. |
| CP-09 | Dos intervalos distintos del mismo empleado y día | Se conservan ambos sin marcarlos como duplicados exactos; aprobado automáticamente. La legitimidad del caso debe confirmarla quien administra el proceso. |
| CP-10 | Importación de horas con espacios en el valor original | La consulta usa la hora normalizada y la trazabilidad conserva el valor original importado; aprobado automáticamente. |
| CP-11 | Clasificación horaria en límites 06:00/19:00, periodos mixtos y cruce de medianoche | Se calculan minutos diurnos y nocturnos como dato derivado, sin alterar marcaciones ni liquidar nómina; aprobado automáticamente. |

La suite también cubre mapeo, vista previa y trazabilidad minimizada de
importaciones sintéticas, exclusión de columnas personales, normalización no
destructiva, una importación de 50 filas sintéticas, migración aditiva, campos
F-012/F-074, el fixture sintético integral, eliminación segura, navegación
clicable y desplazable en ventanas cortas, y exportación desde la interfaz.
Incluye cinco pruebas específicas de empleados: alta y consulta, búsqueda y
filtro por estado, edición, rechazo de datos obligatorios/código duplicado y
protección al eliminar registros con historial. La prueba visual sintética
comprueba el dibujo del logotipo e iconos; otra verifica que hover no cambie
color ni geometría del botón. También incluye informes
filtrados de permisos y horas extra que omiten nombres y texto libre sensible.
Estas pruebas demuestran comportamiento funcional en un entorno local
controlado; no son pruebas con datos reales ni demuestran por sí mismas
validación en un entorno relevante.

### Revisión manual exploratoria

El 20 de noviembre de 2026, una persona usuaria que indicó que sus funciones
se relacionan con asistencia, permisos y horas extra revisó el prototipo con
datos ficticios. La revisión fue limitada: observó la clasificación de una
jornada 22:00–06:00 como nocturna y las alertas de datos que requieren
revisión. Comentó que le pareció clara esa clasificación, entendió que el
sistema busca facilitar la gestión de asistencias, permisos y horas extra, y
sugirió que las alertas expliquen el problema y qué revisar, y que la consulta
de horas trabajadas sea sencilla. Indicó que no revisó todas las opciones.

Este comentario es una revisión exploratoria de uso con datos ficticios, no
una aceptación institucional, una evaluación de todos los flujos ni una
validación integral de importación a exportación. La prueba manual completa
de la interfaz sigue pendiente; no se atribuyen a la persona usuaria tareas
que no reportó haber realizado.

La aplicación no ofrece una operación para editar una marcación existente.
En importaciones se conserva el valor original junto al valor normalizado; la
forma de registrar una corrección después de importar requiere una decisión
documentada del responsable del proceso antes de implementar o aceptar ese
flujo.

### Clasificación informativa de horas diurnas y nocturnas

La aplicación presenta una clasificación derivada de la duración entre las
marcaciones: diurna de 06:00 a 19:00 y nocturna de 19:00 a 06:00 del día
siguiente, de acuerdo con el artículo 160 del Código Sustantivo del Trabajo,
modificado por el artículo 10 de la
[Ley 2466 de 2025](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=260676).
Los límites se tratan como intervalos: 06:00 inicia el tramo diurno y 19:00
inicia el nocturno. Una salida anterior a la entrada se calcula como cruce al
día siguiente solo para esta clasificación; la fecha y las horas originales
se conservan y la alerta de revisión permanece.

El resultado se muestra en formato `hh:mm` en la vista previa, la consulta y
las exportaciones. Es tiempo bruto entre marcaciones: no descuenta pausas ni
determina recargos, horas extra, pagos o liquidación de nómina. Si las horas
faltan, no son válidas o son iguales, la clasificación queda vacía para no
presentar un cálculo ambiguo. La interpretación de jornadas y las políticas
de pausas deben confirmarse con la persona responsable del proceso.

### Limitaciones de validación y estado TRL

No se declara alcanzado ni certificado TRL 5. Las 79 pruebas automatizadas se
ejecutan localmente con datos sintéticos; por sí solas no demuestran validación
en un entorno relevante. La evaluación de Fase 3 ubicó el trabajo cerca de TRL 2,
en avance hacia TRL 3. La implementación y las pruebas locales actuales aportan
evidencia funcional, pero no permiten afirmar TRL 5. La aplicación tampoco
tiene autenticación de usuarios, por lo que no se deben cargar registros
personales reales en ella ni en GitHub.

Para evaluar TRL 5 se requiere, antes de cualquier prueba con datos de la
empresa:

1. Autorización escrita que delimite el propósito, los datos permitidos, las
   personas con acceso, el almacenamiento, la retención y la eliminación.
2. Un entorno de prueba pertinente y controlado, y participación autorizada de
   usuarios que representen el proceso objetivo. Si no se autorizan datos
   reales, se pueden usar casos sintéticos en ese entorno y declarar claramente
   el alcance de esa validación.
3. Medidas adecuadas de acceso y protección. Antes de usar datos personales se
   debe resolver la falta de autenticación de la aplicación y proteger el
   dispositivo y la base de datos.
4. Protocolo con requisitos y resultados esperados definidos previamente;
   pruebas observadas de registros válidos e incompletos, posibles duplicados,
   permisos y horas extra; revisión humana de alertas; y registro de resultados,
   defectos y ajustes.
5. Evidencias autorizadas de la ejecución y aceptación de los usuarios, sin
   publicar datos identificables ni registros de la empresa en el repositorio.

Antes de cerrar las reglas de validación también deben definirse y probarse, con
casos exclusivamente sintéticos, la diferencia entre duplicados y marcaciones
legítimas repetidas, las jornadas que cruzan medianoche, las marcaciones
corregidas y la conservación del valor original frente al valor organizado.
Mientras no se acuerden esas reglas, las situaciones ambiguas solo se señalan
para revisión humana.

Hasta completar y documentar esas validaciones, el resultado se limita a un
prototipo funcional probado localmente con datos sintéticos. No se afirma que
represente todo el proceso real, que calcule nómina o que reduzca errores o
tiempos administrativos.

## Metodología de desarrollo e integración con CDIO

El desarrollo sigue el prototipado incremental aprobado en la Fase 3. CDIO se
utiliza como marco de ingeniería del proyecto, no como metodología de desarrollo
de software. El equipo registra incrementos funcionales, no sprints:

1. **Incremento 1 — Organización de asistencia:** captura, consulta e
   importación controlada de registros sintéticos.
2. **Incremento 2 — Validaciones y alertas:** campos incompletos, formatos no
   reconocidos, códigos sin asociación y posibles duplicados, sin modificar los
   datos ni atribuir causas.
3. **Incremento 3 — Novedades laborales:** formularios de permisos y horas
   extras basados en la estructura de F-012 y F-074, probados únicamente con
   información ficticia.
4. **Incremento 4 — Consultas y reportes:** filtros, resúmenes y exportación
   CSV/Excel de los datos sintéticos disponibles.

Cada incremento se documenta mediante sus requisitos, decisiones de diseño,
funciones implementadas, casos de prueba, resultados y ajustes. La articulación
con CDIO comprende concebir el problema y los límites, diseñar datos e
interfaces, implementar los incrementos y operar/evaluar el prototipo en un
entorno controlado. Las pruebas actuales sustentan solo comportamiento local
con datos sintéticos; no acreditan por sí mismas un nivel TRL.

## Seguimiento de la retroalimentación del tutor

| Tema | Evidencia disponible | Pendiente de validación |
|---|---|---|
| Jornada que cruza medianoche | Caso sintético 22:00–06:00: se conserva la fecha informada y se genera una alerta neutral; no se deduce otra fecha. | Acordar con la persona responsable cómo interpretar la jornada y registrar la decisión del usuario. |
| Repetición legítima y duplicidad | Los registros exactos coincidentes se conservan y señalan; dos intervalos distintos en el día no se clasifican como duplicados exactos. | Confirmar los criterios del proceso para repetición legítima y duplicados. |
| Corrección de registros | La importación conserva valores originales y normalizados. La interfaz no incluye edición de marcaciones. | Definir un flujo de corrección trazable y validarlo antes de implementarlo o usarlo. |
| Recorrido de interfaz | Hay cobertura automatizada de importación, vista previa, persistencia, consultas y exportaciones; también se realizó una revisión exploratoria limitada con datos ficticios. | Sigue pendiente el recorrido observado de extremo a extremo, desde la importación hasta la exportación. |
| Respaldo y recuperación | Se ejecutó una copia y restauración SQLite en una base temporal sintética; `integrity_check` dio `ok` y se recuperaron 1 empleado, 3 asistencias y 1 lote. | Acordar acceso y retención con el responsable; la prueba no fue una recuperación manual de la interfaz ni de datos de producción. |
| Validación y aceptación | Pruebas automatizadas locales y comentarios exploratorios de una persona usuaria que indicó relación de sus funciones con el proceso; observó la clasificación nocturna y las alertas. | La revisión fue limitada, no cubrió todas las opciones ni constituye aceptación institucional o evidencia suficiente para declarar TRL 5. |
| Aportes por incremento | La matriz técnica enlaza incrementos con requisitos y pruebas. | Deisy y Lina deben confirmar sus aportes individuales y evidencias; no se atribuyen actividades sin confirmación. |
| Entregables | El código está en el [repositorio público de NEXORA HR](https://github.com/lorena23234/Nexora); la grabación local del video ya se realizó. | Revisar el archivo, subirlo a una plataforma accesible al tutor y añadir el enlace de visualización. |

Las pruebas automatizadas y la revisión exploratoria limitada de una persona
usuaria no sustituyen el recorrido manual integral ni demuestran aceptación
institucional o validación en el entorno relevante. El estado TRL 5 no se
declara demostrado.

### Preparación del recorrido manual sintético

El archivo [asistencia_manual_sintetica.csv](tests/fixtures/asistencia_manual_sintetica.csv)
contiene tres filas ficticias. Para mantener la prueba aislada, en PowerShell
define una base temporal y ejecuta la aplicación:

```powershell
$env:NEXORA_HR_DB_PATH = Join-Path $env:TEMP 'nexora_hr_ui_synthetic_20261120.db'
.\.venv\Scripts\python.exe main.py
```

Para completar el recorrido integral que aún está pendiente, crea primero el
empleado ficticio `DEMO-UI-001` (por ejemplo,
“Empleado Sintético UI”), importa el CSV desde Asistencia, revisa el mapeo y la
vista previa, clasifica la fuente como datos sintéticos y confirma. Comprueba
las tres filas; las dos franjas distintas del 19 de noviembre no deben
marcarse como duplicado exacto y cada una debe mostrar 04:00 diurnas y 00:00
nocturnas. La fila 22:00–06:00 debe conservar la fecha y las horas, mostrar
00:00 diurnas y 08:00 nocturnas e indicar el posible cruce de medianoche o
inconsistencia. Cambia de sección y regresa, aplica un filtro y exporta el
resultado. Registra el resultado observado; no describas pasos no ejecutados
como aprobados.

Antes de una sesión con usuarios, cierra la aplicación y realiza el respaldo
mediante la API `sqlite3.Connection.backup()` a un archivo distinto. Verifica
`PRAGMA integrity_check` y restaura el respaldo en otra ruta temporal, nunca
sobre la base original. Esta copia/restauración se probó con los datos
sintéticos anteriores; el acceso, la retención y el procedimiento para una
sesión del proceso objetivo aún requieren acuerdo con la persona responsable.

## Repositorio de GitHub

El código fuente, las dependencias declaradas y las pruebas sintéticas están
publicados en el repositorio público
[lorena23234/Nexora](https://github.com/lorena23234/Nexora), en la rama
`master`. `.gitignore` excluye bases y carpetas locales, exportaciones,
documentos de oficina, grabaciones y subtítulos, archivos temporales,
credenciales y entornos virtuales. No se publican bases de datos locales,
fuentes documentales ni registros reales.
