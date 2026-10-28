# ClapLauncher

Lanza tus aplicaciones con un chasquido de dedos. Se queda escuchando el micrófono y, en cuanto detecta el chasquido, abre la lista de aplicaciones que tengas configurada.

Funciona en Windows, macOS y Linux.

## Cómo funciona

- **Detección por transitorio**: mide el pico de la diferencia entre muestras seguidas, lo que actúa como filtro paso alto. Un chasquido es agudo y de ataque muy rápido, así que destaca claramente sobre la voz o los golpes sordos.
- **Umbral adaptativo**: aprende el nivel de ruido de fondo sobre la marcha y dispara cuando un bloque lo supera `sensitivity` veces. No hay que calibrar a mano ni depende del volumen del micrófono.
- **Multiplataforma**: acepta ejecutables, accesos directos (`.lnk`), URIs (`ms-teams:`), aplicaciones de macOS (`.app`), carpetas y comandos con argumentos.

## Requisitos

- Python 3.9 o superior
- `numpy` y `sounddevice` (que necesita PortAudio)

En Linux, si PortAudio no está instalado:

```bash
sudo apt install libportaudio2
```

## Instalación

```bash
git clone https://github.com/<tu-usuario>/clap_launcher.git
cd clap_launcher
pip install -r requirements.txt
```

## Uso

```bash
python clap_launcher.py                      # escucha y abre tus apps
python clap_launcher.py --test               # modo prueba: muestra el nivel y NO abre nada
python clap_launcher.py --install-autostart  # arranca con el ordenador
python clap_launcher.py --remove-autostart   # quita el arranque automático
```

En Windows, si `python` apunta al alias de la Microsoft Store (da error al ejecutar), usa el lanzador:

```powershell
py clap_launcher.py
```

## Calibrar la sensibilidad

```powershell
py clap_launcher.py --test
```

La barra se llena justo en el punto en el que dispararía:

```
  nivel 0.132 ( 44.0x ruido) |██████████████████████████████          |
```

- Si salta sin querer (por ejemplo al teclear), sube `sensitivity`.
- Si no te pilla el chasquido, bájala.

## Configuración

Todo se ajusta en `config.json`, junto al script:

```json
{
  "apps": [
    "ms-teams:",
    "%LOCALAPPDATA%/Programs/Trae/Trae.exe"
  ],
  "sensitivity": 12.0,
  "events": 1,
  "min_gap": 0.12,
  "max_gap": 0.8,
  "delay_between_apps": 0.5,
  "exit_after_launch": true,
  "max_listen_minutes": 0
}
```

| Clave | Por defecto | Descripción |
| --- | --- | --- |
| `apps` | `[]` | Aplicaciones a abrir, en orden. Admite variables de entorno (`%LOCALAPPDATA%`) y `~`. |
| `sensitivity` | `12.0` | Veces por encima del ruido ambiente que debe destacar el chasquido. |
| `events` | `1` | Número de chasquidos necesarios para lanzar. |
| `min_gap` | `0.12` | Segundos mínimos entre chasquidos (evita contar el eco). |
| `max_gap` | `0.8` | Segundos máximos entre chasquidos de una misma secuencia. |
| `delay_between_apps` | `0.5` | Espera entre una aplicación y la siguiente. |
| `exit_after_launch` | `true` | Cierra el proceso después de abrir las aplicaciones. |
| `max_listen_minutes` | `0` | Minutos máximos de escucha. `0` = indefinidamente. |

## Arranque automático

El comando `--install-autostart` crea el archivo correspondiente a cada sistema:

| Sistema | Ruta |
| --- | --- |
| Windows | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClapLauncher.vbs` |
| macOS | `~/Library/LaunchAgents/com.claplauncher.plist` |
| Linux | `~/.config/autostart/claplauncher.desktop` |

En Windows se lanza con `pythonw.exe`, así que no aparece ninguna ventana de consola. Para deshacerlo:

```powershell
py clap_launcher.py --remove-autostart
```

## Problemas frecuentes

| Problema | Solución |
| --- | --- |
| `No se pudo abrir el micrófono` | Revisa el dispositivo de entrada por defecto y que la aplicación tenga permiso para usarlo. |
| Se lanza sin hacer el chasquido | Sube `sensitivity`. |
| No detecta el chasquido | Baja `sensitivity`, acércate al micrófono y comprueba el nivel con `--test`. |
| Una aplicación no se abre | Se muestra un aviso con la entrada que falló; revisa que la ruta o el comando existan en tu equipo. |
