"""Caja de arena para ejecutar código Python sin riesgo.

Usa `bubblewrap` (bwrap): un espacio de nombres aparte con la red cortada, el
disco casi todo de solo lectura y un directorio de trabajo desechable. Lo que
corre dentro no puede tocar `/home`, ni abrir conexiones, ni quedarse colgado:
si tarda más de la cuenta, se mata.

Es la pieza que pide el hackatón (ejecutar código de verdad, con registro) y
la que protege este portátil mientras yo pruebo lo que genero.

    from sandbox import Sandbox
    r = Sandbox().ejecutar("print(6*7)")
    r.ok, r.salida  # True, '42\\n'
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Sandbox", "Resultado", "ErrorSandbox", "bwrap_disponible"]

# Sitios del sistema que hace falta ver desde dentro para que Python arranque.
RUTAS_SISTEMA = ("/usr", "/lib", "/lib64", "/bin", "/sbin")


class ErrorSandbox(RuntimeError):
    """El aislamiento no está disponible o no se pudo montar."""


def bwrap_disponible() -> bool:
    """¿Está instalado `bwrap` en este equipo?"""
    return shutil.which("bwrap") is not None


@dataclass
class Resultado:
    """Lo que devolvió una ejecución dentro de la caja."""

    codigo: int
    salida: str
    errores: str
    segundos: float
    orden: list[str] = field(default_factory=list)
    agotado: bool = False

    @property
    def ok(self) -> bool:
        return self.codigo == 0 and not self.agotado

    def como_diccionario(self) -> dict:
        return {
            "ok": self.ok,
            "codigo": self.codigo,
            "salida": self.salida,
            "errores": self.errores,
            "segundos": round(self.segundos, 3),
            "agotado": self.agotado,
            "orden": self.orden,
        }


class Sandbox:
    """Ejecuta código Python aislado.

    Args:
        memoria_mb: tope de memoria del proceso hijo.
        segundos: tiempo máximo de ejecución (CPU y reloj).
        tamano_fichero_mb: tope de escritura por fichero.
    """

    def __init__(self, memoria_mb: int = 512, segundos: int = 10,
                 tamano_fichero_mb: int = 10) -> None:
        if not bwrap_disponible():
            raise ErrorSandbox(
                "Falta 'bubblewrap'. Instálalo con: sudo apt install bubblewrap"
            )
        if memoria_mb < 64:
            raise ValueError("memoria_mb demasiado bajo (mínimo 64)")
        self.memoria_mb = memoria_mb
        self.segundos = segundos
        self.tamano_fichero_mb = tamano_fichero_mb

    # -- orden de arranque -------------------------------------------------

    def _orden_bwrap(self, trabajo: Path) -> list[str]:
        orden = [
            "bwrap",
            "--die-with-parent",
            "--new-session",
            "--unshare-all",          # red, pid, ipc, uts, cgroup y usuario
            "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "HOME", "/trabajo",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
        ]
        for ruta in RUTAS_SISTEMA:
            orden += ["--ro-bind-try", ruta, ruta]
        orden += ["--bind", str(trabajo), "/trabajo", "--chdir", "/trabajo"]
        return orden

    def _orden_python(self) -> list[str]:
        # Los límites se ponen dentro porque bwrap no los cambia él solo.
        limpieza = (
            f"ulimit -v {self.memoria_mb * 1024}; "
            f"ulimit -t {self.segundos}; "
            f"ulimit -f {self.tamano_fichero_mb * 1024}; "
            "exec python3 main.py"
        )
        return ["bash", "-c", limpieza]

    # -- ejecución ---------------------------------------------------------

    def ejecutar(self, codigo: str, archivos: dict[str, str] | None = None) -> Resultado:
        """Ejecuta `codigo` como `main.py` con los `archivos` de apoyo.

        Args:
            codigo: contenido del programa.
            archivos: otros ficheros a dejar en el directorio de trabajo
                (por ejemplo el HTML que se quiere revisar).

        Returns:
            Resultado con lo impreso, el código de salida y el tiempo.
        """
        if not codigo.strip():
            raise ValueError("el código está vacío")

        with tempfile.TemporaryDirectory(prefix="sitios-sandbox-") as tmp:
            trabajo = Path(tmp)
            (trabajo / "main.py").write_text(codigo, encoding="utf-8")
            for nombre, contenido in (archivos or {}).items():
                destino = trabajo / nombre
                if trabajo.resolve() not in destino.resolve().parents:
                    raise ValueError(f"ruta no permitida: {nombre}")
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(contenido, encoding="utf-8")

            orden = self._orden_bwrap(trabajo) + self._orden_python()
            inicio = time.monotonic()
            try:
                proceso = subprocess.run(
                    orden, capture_output=True, text=True, timeout=self.segundos + 5
                )
                codigo_salida, salida, errores = (
                    proceso.returncode, proceso.stdout, proceso.stderr
                )
                agotado = False
            except subprocess.TimeoutExpired as fallo:
                codigo_salida = -9
                salida = (fallo.stdout or b"").decode() if isinstance(fallo.stdout, bytes) else (fallo.stdout or "")
                errores = (fallo.stderr or b"").decode() if isinstance(fallo.stderr, bytes) else (fallo.stderr or "")
                agotado = True
            except FileNotFoundError as fallo:
                raise ErrorSandbox(f"no se pudo lanzar bwrap: {fallo}") from fallo

            return Resultado(
                codigo=codigo_salida,
                salida=salida,
                errores=errores,
                segundos=time.monotonic() - inicio,
                orden=["bwrap (red cortada, /home oculto, /trabajo temporal)",
                       "python3 main.py"] + [f"archivo: {n}" for n in (archivos or {})],
                agotado=agotado,
            )
