"""
Modulo Utility per PyExplorer.
Contiene funzioni stateless per la gestione del sistema locale.

Versione: 0.1.1
"""
import os
import platform
import subprocess
import stat

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
    return stat.filemode(mode)

def format_size(size_bytes: int) -> str:
    """Formatta la dimensione dei file in formato leggibile."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"