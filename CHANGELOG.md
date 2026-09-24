# Historial de versiones

## 2.0.0 — 2026-09-24

Primera publicación de Minecraft AFK en GitHub Releases. La etiqueta `v2.0.0` coincide con la versión que ya declara la aplicación.

Esta versión reúne una interfaz GTK3 para Linux, ataques automáticos con Mob Farm y minado continuo con Stone Farm. Incluye configuración del pico y sus encantamientos, estimación de durabilidad, calibración de la granja, preparación de 20 segundos para el minado, temporizador y parada automática. Las pestañas de estado y registros permiten consultar la ejecución, y los controles de parada solicitan la liberación del botón izquierdo.

La interfaz y los mensajes de los scripts están disponibles en español e inglés, con detección automática y selección persistente en Ajustes. El cambio de idioma se aplica al reiniciar la aplicación. El paquete incluye los catálogos gettext compilados, el README, la guía de contribución, las pruebas y la licencia MIT.

Se distribuyen paquetes `.tar.gz` y `.zip` para Linux, junto con `SHA256SUMS`. Contienen la aplicación en Python y requieren Python 3.10 o posterior, GTK3, sus enlaces de Python, Bash y `xdotool`, en una sesión X11. El temporizador sigue siendo una estimación: Unbreaking introduce variación aleatoria y Mending no se incluye en el modelo. Cerrar la ventana no detiene una granja activa; utiliza sus controles de parada o `emergency-stop`.
