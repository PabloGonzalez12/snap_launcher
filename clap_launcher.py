#!/usr/bin/env python3
"""
ClapLauncher - das un chasquido de dedos y se abren tus aplicaciones.

Uso:
    python clap_launcher.py                     # escucha y lanza las apps
    python clap_launcher.py --test              # muestra el nivel del micro y detecta chasquidos SIN lanzar nada
    python clap_launcher.py --install-autostart # arranca con el ordenador
    python clap_launcher.py --remove-autostart  # quita el arranque automático

La configuración está en config.json (junto a este archivo).
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"

DEFAULTS = {
    "apps": [],
    "sensitivity": 12.0,     # veces por encima del ruido ambiente que debe destacar un chasquido
    "events": 1,             # número de chasquidos necesarios
    "min_gap": 0.12,         # segundos mínimos entre chasquidos (evita contar el eco)
    "max_gap": 0.8,          # segundos máximos entre chasquidos
    "delay_between_apps": 0.5,
    "exit_after_launch": True,
    "max_listen_minutes": 0,  # 0 = escuchar indefinidamente
}


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        print(f"[!] No encuentro {CONFIG_PATH}, uso valores por defecto.")
    return cfg


# --------------------------------------------------------------------------
# Detección de chasquidos
# --------------------------------------------------------------------------
def transient_level(block):
    """Nivel de transitorio de un bloque: pico de la diferencia entre muestras.

    Restar muestras seguidas hace de filtro paso alto, así que realza los
    chasquidos (agudos y muy cortos) frente a la voz o los golpes sordos.
    """
    return float(np.max(np.abs(np.diff(block[:, 0]))))


class SnapDetector:
    """Detecta chasquidos de dedos comparándolos con el ruido ambiente.

    En lugar de un umbral fijo medimos cuánto destaca cada bloque sobre el
    ruido de fondo, que se aprende sobre la marcha: así no hay que calibrar
    a mano ni depende del volumen del micrófono.
    """

    MIN_NOISE = 0.002  # suelo de ruido: en salas muy silenciosas evita disparar con cualquier golpecito

    def __init__(self, sensitivity, events, min_gap, max_gap):
        self.sensitivity = sensitivity
        self.needed = events
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.ruido = self.MIN_NOISE  # ruido de fondo estimado (se adapta solo)
        self.times = []
        self.last_snap = 0.0

    def _aprender_ruido(self, nivel):
        """Sigue el ruido ambiente: sube muy despacio y baja rápido."""
        ritmo = 0.02 if nivel > self.ruido else 0.1
        self.ruido = max(self.ruido + (nivel - self.ruido) * ritmo, self.MIN_NOISE)

    def umbral(self):
        """Nivel que debe superar un bloque para contar como chasquido."""
        return self.ruido * self.sensitivity

    def feed(self, nivel, now):
        """Devuelve (chasquido_detectado, secuencia_completa)."""
        self._aprender_ruido(nivel)

        if nivel < self.umbral() or now - self.last_snap < self.min_gap:
            return False, False

        self.last_snap = now
        if self.times and now - self.times[-1] > self.max_gap:
            self.times = []  # pasó demasiado tiempo, empezamos de nuevo
        self.times.append(now)

        if len(self.times) >= self.needed:
            self.times = []
            return True, True
        return True, False


# --------------------------------------------------------------------------
# Lanzador de aplicaciones (multiplataforma)
# --------------------------------------------------------------------------
def launch(entry):
    entry = os.path.expandvars(os.path.expanduser(entry))
    try:
        if sys.platform == "win32":
            try:
                # Funciona con .exe, .lnk (accesos directos), URIs (ms-teams:) y carpetas
                os.startfile(entry)
            except (FileNotFoundError, OSError):
                # Si lleva argumentos (ej. 'code C:/proyecto'), lo lanzamos como comando
                subprocess.Popen(entry, shell=True)
        elif sys.platform == "darwin":
            if entry.endswith(".app") or "/" not in entry and " " not in entry:
                subprocess.Popen(["open", "-a", entry])
            else:
                subprocess.Popen(entry, shell=True)
        else:
            subprocess.Popen(entry, shell=True, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  ✔ {entry}")
    except Exception as e:  # una app que falla no debe parar las demás
        print(f"  ✘ {entry} -> {e}")


def launch_all(cfg):
    print("🫰 ¡Chasquido detectado! Abriendo aplicaciones...")
    for app in cfg["apps"]:
        launch(app)
        time.sleep(cfg["delay_between_apps"])


# --------------------------------------------------------------------------
# Bucle principal
# --------------------------------------------------------------------------
def run(cfg, test_mode=False):
    detector = SnapDetector(cfg["sensitivity"], cfg["events"], cfg["min_gap"], cfg["max_gap"])
    triggered = threading.Event()
    peak = {"level": 0.0}

    def callback(indata, frames, time_info, status):
        level = transient_level(indata)  # pico agudo del bloque
        peak["level"] = max(peak["level"], level)
        snap, done = detector.feed(level, time.monotonic())
        if test_mode and snap:
            print(f"\n  🫰 chasquido (nivel {level:.3f})")
        if done:
            triggered.set()

    device_info = sd.query_devices(kind="input")
    samplerate = int(device_info["default_samplerate"])
    blocksize = int(samplerate * 0.02)  # bloques de 20 ms: consumo de CPU casi nulo

    print(f"🎙  Escuchando con: {device_info['name']}")
    print(f"    Sensibilidad: {cfg['sensitivity']}x ruido | Chasquidos: {cfg['events']}")
    if test_mode:
        print("    MODO TEST: no se abrirá nada. Ctrl+C para salir.\n")

    deadline = None
    if cfg["max_listen_minutes"] > 0:
        deadline = time.monotonic() + cfg["max_listen_minutes"] * 60

    with sd.InputStream(channels=1, samplerate=samplerate, blocksize=blocksize,
                        callback=callback):
        while True:
            if triggered.wait(timeout=0.1):
                triggered.clear()
                if test_mode:
                    print("  ✅ Secuencia completa detectada (en modo normal se abrirían las apps)\n")
                else:
                    launch_all(cfg)
                    if cfg["exit_after_launch"]:
                        print("Hecho. Cerrando proceso.")
                        return
            if test_mode:
                ratio = peak["level"] / max(detector.ruido, 1e-9)
                bar = "█" * int(min(peak["level"] / detector.umbral(), 1.0) * 40)
                print(f"\r  nivel {peak['level']:.3f} ({ratio:5.1f}x ruido) |{bar:<40}|",
                      end="", flush=True)
                peak["level"] = 0.0
            if deadline and time.monotonic() > deadline:
                print("Tiempo máximo de escucha alcanzado. Cerrando.")
                return


# --------------------------------------------------------------------------
# Arranque automático
# --------------------------------------------------------------------------
def _autostart_target():
    script = str(Path(__file__).resolve())
    if sys.platform == "win32":
        pythonw = Path(sys.executable).with_name("pythonw.exe")  # sin ventana de consola
        py = str(pythonw if pythonw.exists() else sys.executable)
        folder = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
        return py, script, folder / "ClapLauncher.vbs"
    if sys.platform == "darwin":
        return sys.executable, script, Path.home() / "Library/LaunchAgents/com.claplauncher.plist"
    return sys.executable, script, Path.home() / ".config/autostart/claplauncher.desktop"


def install_autostart():
    py, script, target = _autostart_target()
    target.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        content = ('Set sh = CreateObject("WScript.Shell")\r\n'
                   f'sh.Run """{py}"" ""{script}""", 0, False\r\n')
    elif sys.platform == "darwin":
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.claplauncher</string>
<key>ProgramArguments</key><array><string>{py}</string><string>{script}</string></array>
<key>RunAtLoad</key><true/>
</dict></plist>
"""
    else:
        content = ("[Desktop Entry]\nType=Application\nName=ClapLauncher\n"
                   f"Exec={py} {script}\nX-GNOME-Autostart-enabled=true\n")
    target.write_text(content, encoding="utf-8")
    print(f"✔ Arranque automático instalado: {target}")


def remove_autostart():
    _, _, target = _autostart_target()
    if target.exists():
        target.unlink()
        print(f"✔ Eliminado: {target}")
    else:
        print("No había arranque automático instalado.")


def main():
    parser = argparse.ArgumentParser(description="Abre tus apps con un chasquido de dedos.")
    parser.add_argument("--test", action="store_true", help="modo prueba: muestra el nivel y no abre nada")
    parser.add_argument("--install-autostart", action="store_true")
    parser.add_argument("--remove-autostart", action="store_true")
    args = parser.parse_args()

    if args.install_autostart:
        return install_autostart()
    if args.remove_autostart:
        return remove_autostart()

    try:
        run(load_config(), test_mode=args.test)
    except KeyboardInterrupt:
        print("\nAdiós 👋")
    except sd.PortAudioError as e:
        print(f"[!] No se pudo abrir el micrófono: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
