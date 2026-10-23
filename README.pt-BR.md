<div align="center">

# Flyto2 × ROS 2 Robots

**Diga ao seu robô ROS 2 aonde ir. Ele vai sozinho, dá uma olhada e prova que chegou.**

![Flyto2 device pack](https://img.shields.io/badge/Flyto2-device%20pack-6d5dfc) ![ROS 2](https://img.shields.io/badge/ROS%202-Nav2-22314e) ![Open-RMF](https://img.shields.io/badge/Open--RMF-fleets-0a7d6e) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md) · **Português (BR)**

[Início rápido](#início-rápido) · [Destaques](#destaques) · [Como funciona](#como-funciona) · [Para desenvolvedores](#para-desenvolvedores)

</div>

## Início rápido

```bash
# in the Python environment that runs Flyto2
pip install "git+https://github.com/flytohub/flyto-modules-robotics"
git clone https://github.com/flytohub/flyto-robotics && pip install -e ./flyto-robotics   # the ROS 2 adapter
export FLYTO_ROS2_SSH_HOST=ubuntu@my-robot.local                                        # your robot
```

Adicione o robô a um Space do Flyto2 e diga:

> Vai até a cozinha e tira uma foto.

## Destaques

- **É só falar.** "Vai até a cozinha e tira uma foto." O robô cuida do resto.
- **Zero código do Flyto2 no robô.** Ele continua com o ROS 2 de fábrica. Nada pra gravar, nada pra ficar de olho.
- **Chegada com prova.** O Flyto2 confere a posição no mapa por conta própria. O robô dizer "cheguei" não basta.
- **Conhece seus lugares pelo nome.** Cozinha, base de carga, porta da frente. Salve um lugar uma vez e mande ele pra lá quando quiser.
- **Se vira quando trava.** Caminho bloqueado? Ele volta com um desvio até o mesmo destino.
- **Parar é parar.** O comando de parada sai na hora. Nunca espera aprovação.
- **De um robô a uma frota inteira.** Frotas Open-RMF usam exatamente as mesmas habilidades.

## Como funciona

1. Você diz o que quer.
2. O Flyto2 transforma em passos e confere as permissões.
3. O adaptador ROS 2 no seu computador comanda o Nav2 do robô.
4. O Flyto2 confere a posição no mapa antes de dar como feito.

---

## Para desenvolvedores

Capacidades, segurança, configuração e testes estão na versão em inglês. [README.md → For developers](README.md#for-developers)

License: Apache-2.0 (`LICENSE`).
