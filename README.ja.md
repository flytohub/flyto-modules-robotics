<div align="center">

# Flyto2 × ROS 2 Robots

**ROS 2 ロボットに行き先を伝えるだけ。走って、見て、着いたことまで証明する。**

![Flyto2 device pack](https://img.shields.io/badge/Flyto2-device%20pack-6d5dfc) ![ROS 2](https://img.shields.io/badge/ROS%202-Nav2-22314e) ![Open-RMF](https://img.shields.io/badge/Open--RMF-fleets-0a7d6e) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

[English](README.md) · **日本語** · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md) · [Português (BR)](README.pt-BR.md)

[クイックスタート](#クイックスタート) · [特長](#特長) · [しくみ](#しくみ) · [開発者向け](#開発者向け)

</div>

## クイックスタート

```bash
# in the Python environment that runs Flyto2
pip install "git+https://github.com/flytohub/flyto-modules-robotics"
git clone https://github.com/flytohub/flyto-robotics && pip install -e ./flyto-robotics   # the ROS 2 adapter
export FLYTO_ROS2_SSH_HOST=ubuntu@my-robot.local                                        # your robot
```

ロボットを Flyto2 の Space に追加して、こう言うだけ：

> キッチンに行って写真を撮って。

## 特長

- **言うだけ。** 「キッチンに行って写真を撮って」。あとはロボットにおまかせ。
- **ロボットに Flyto2 のコードはゼロ。** 純正の ROS 2 のまま。書き換えも、お守りも不要。
- **到着は証拠つき。** Flyto2 が地図上の位置を自分で確かめる。ロボットの「着きました」だけでは認めない。
- **場所を名前で覚える。** キッチン、充電台、玄関。一度登録すれば、いつでもそこへ。
- **自力で切り抜ける。** 道がふさがれても、同じゴールへの回り道を持ち帰る。
- **止めたら止まる。** 停止は即座に送信。承認待ちで遅れることはない。
- **1台から、フリートまで。** Open-RMF のフリートもまったく同じスキルで動く。

## しくみ

1. やってほしいことを言う。
2. Flyto2 が手順に分解し、権限を確認する。
3. 手元のコンピューターの ROS 2 アダプターが、ロボットの Nav2 を動かす。
4. Flyto2 が地図上の位置を自分で確かめてから、完了とする。

---

## 開発者向け

能力の一覧、安全の仕組み、設定、テストの詳細は英語版にあります。 [README.md → For developers](README.md#for-developers)

License: Apache-2.0 (`LICENSE`).
