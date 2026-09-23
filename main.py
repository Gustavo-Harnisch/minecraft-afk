#!/usr/bin/env python3
"""Punto de entrada de la interfaz GTK de Minecraft AFK."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from minecraft_afk.window import MinecraftAfkWindow


# Alias de compatibilidad para cualquier código que importara la clase desde
# main.py antes de la modularización.
MinecraftAfkApp = MinecraftAfkWindow


def main() -> None:
    window = MinecraftAfkWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
