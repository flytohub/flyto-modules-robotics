<div align="center">

# Flyto2 × ROS 2 Robots

**告诉你的 ROS 2 机器人去哪儿。它自己开过去、看一眼，还能证明自己真的到了。**

![Physical AI](https://img.shields.io/badge/Physical%20AI-ROS%202-6d5dfc) ![ROS 2](https://img.shields.io/badge/ROS%202-Nav2-22314e) ![Open-RMF](https://img.shields.io/badge/Open--RMF-fleets-0a7d6e) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

[English](README.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **简体中文** · [Español](README.es.md) · [Português (BR)](README.pt-BR.md)

[快速开始](#快速开始) · [特性](#特性) · [工作原理](#工作原理) · [开发者](#开发者)

</div>

## 快速开始

```bash
# in the Python environment that runs Flyto2
pip install "git+https://github.com/flytohub/flyto-modules-robotics"
git clone https://github.com/flytohub/flyto-robotics && pip install -e ./flyto-robotics   # the ROS 2 adapter
export FLYTO_ROS2_SSH_HOST=ubuntu@my-robot.local                                        # your robot
```

把机器人加入 Flyto2 Space，然后说：

> 去厨房拍一张照片。

## 特性

- **说一句就行**：“去厨房拍一张照片”，剩下的交给机器人。
- **机器人上零 Flyto2 代码**：继续跑原厂 ROS 2，不用刷机，也不用守着。
- **到达有证据**：Flyto2 自己核对地图上的位置，机器人说“我到了”不算数。
- **按名字记住地点**：厨房、充电座、门口，存一次，随时派它过去。
- **被挡住会自己绕**：路被堵住时，会带回一条通往同一目的地的绕行路线。
- **说停就停**：停止指令立即发出，绝不等待审批。
- **一台到整个车队**：Open-RMF 车队用的是完全相同的技能。

## 工作原理

1. 你用一句话说出要做的事。
2. Flyto2 拆成步骤并检查权限。
3. 你电脑上的 ROS 2 适配器驱动机器人的 Nav2。
4. Flyto2 自己核对地图位置，确认后才算完成。

---

## 开发者

能力表、安全机制、配置与测试的细节在英文版里。 [README.md → For developers](README.md#for-developers)

License: Apache-2.0 (`LICENSE`).
