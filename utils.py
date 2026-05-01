"""
Modulo Utility per PyExplorer.
Contiene funzioni stateless per la gestione del sistema locale.
"""
import os
import platform
import subprocess

def open_local_path(path: str) -> None:
    """
    Apre un file o una cartella utilizzando l'applicazione predefinita del sistema operativo.
    """
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])

def format_permissions(mode: int) -> str:
    """Converte i bit di modo in una stringa leggibile (es. drwxr-xr-x)."""
    import stat
    return stat.filemode(mode)