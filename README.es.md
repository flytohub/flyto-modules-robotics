<div align="center">

# Flyto2 × ROS 2 Robots

**Dile a tu robot ROS 2 adónde ir. Llega solo, echa un vistazo y demuestra que llegó.**

![Flyto2 device pack](https://img.shields.io/badge/Flyto2-device%20pack-6d5dfc) ![ROS 2](https://img.shields.io/badge/ROS%202-Nav2-22314e) ![Open-RMF](https://img.shields.io/badge/Open--RMF-fleets-0a7d6e) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · **Español** · [Português (BR)](README.pt-BR.md)

</div>

## Inicio rápido

```bash
# in the Python environment that runs Flyto2
pip install "git+https://github.com/flytohub/flyto-modules-robotics"
git clone https://github.com/flytohub/flyto-robotics && pip install -e ./flyto-robotics   # the ROS 2 adapter
export FLYTO_ROS2_SSH_HOST=ubuntu@my-robot.local                                        # your robot
```

Añade el robot a un Space de Flyto2 y di:

> Ve a la cocina y haz una foto.

## Lo mejor

- **Solo dilo.** "Ve a la cocina y haz una foto." Tu robot se encarga del resto.
- **Cero código de Flyto2 en el robot.** Sigue con su ROS 2 de fábrica. Nada que flashear, nada que vigilar.
- **Llegadas que se demuestran.** Flyto2 comprueba la posición en el mapa por su cuenta. Que el robot diga "ya llegué" no basta.
- **Se sabe tus lugares por nombre.** Cocina, base de carga, entrada. Guarda un sitio una vez y mándalo allí cuando quieras.
- **Sale solo de los atascos.** ¿Camino bloqueado? Vuelve con un rodeo hacia el mismo destino.
- **Parar es parar.** La orden de parada sale al instante. Nunca espera una aprobación.
- **De un robot a toda una flota.** Las flotas Open-RMF usan exactamente las mismas habilidades.

## Cómo funciona

1. Dices lo que quieres.
2. Flyto2 lo convierte en pasos y revisa los permisos.
3. El adaptador ROS 2 de tu ordenador mueve Nav2 en el robot.
4. Flyto2 comprueba la posición en el mapa y la foto antes de darlo por hecho.

---

## Para desarrolladores

Las capacidades, la seguridad, la configuración y las pruebas están en la versión en inglés. [README.md → For developers](README.md#for-developers)

License: Apache-2.0 (`LICENSE`).
