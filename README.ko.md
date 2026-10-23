<div align="center">

# Flyto2 × ROS 2 Robots

**ROS 2 로봇에게 갈 곳만 말하세요. 직접 가서, 둘러보고, 도착했다는 걸 증명해요.**

![Physical AI](https://img.shields.io/badge/Physical%20AI-ROS%202-6d5dfc) ![ROS 2](https://img.shields.io/badge/ROS%202-Nav2-22314e) ![Open-RMF](https://img.shields.io/badge/Open--RMF-fleets-0a7d6e) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

[English](README.md) · [日本語](README.ja.md) · **한국어** · [简体中文](README.zh-CN.md) · [Español](README.es.md) · [Português (BR)](README.pt-BR.md)

[빠른 시작](#빠른-시작) · [주요 기능](#주요-기능) · [작동 방식](#작동-방식) · [개발자용](#개발자용)

<img src="https://raw.githubusercontent.com/flytohub/flyto-robotics/main/docs/assets/demo-dry-run.gif" alt="A simulated delivery: the robot drives to the pharmacy, stops for an obstacle, then delivers to Ward A" width="760">

</div>

## 빠른 시작

```bash
# in the Python environment that runs Flyto2
pip install "git+https://github.com/flytohub/flyto-modules-robotics"
git clone https://github.com/flytohub/flyto-robotics && pip install -e ./flyto-robotics   # the ROS 2 adapter
export FLYTO_ROS2_SSH_HOST=ubuntu@my-robot.local                                        # your robot
```

로봇을 Flyto2 Space에 추가하고 이렇게 말하면 돼요:

> 주방에 가서 사진 찍어 줘.

## 주요 기능

- **말만 하세요.** "주방에 가서 사진 찍어 줘." 나머지는 로봇이 알아서 해요.
- **로봇에는 Flyto2 코드가 0줄.** 순정 ROS 2 그대로예요. 새로 깔 것도, 붙어서 지켜볼 것도 없어요.
- **도착은 증거로.** Flyto2가 지도 위 위치를 직접 확인해요. 로봇이 "도착했어요"라고만 해서는 안 돼요.
- **장소를 이름으로 기억해요.** 주방, 충전 독, 현관. 한 번 저장하면 언제든 보낼 수 있어요.
- **막혀도 스스로 빠져나와요.** 길이 막히면 같은 목적지로 가는 우회로를 찾아와요.
- **멈추라면 멈춰요.** 정지 명령은 바로 나가요. 승인을 기다리지 않아요.
- **한 대부터 플릿까지.** Open-RMF 플릿도 똑같은 기술로 움직여요.

## 작동 방식

1. 원하는 걸 말해요.
2. Flyto2가 단계로 나누고 권한을 확인해요.
3. 내 컴퓨터의 ROS 2 어댑터가 로봇의 Nav2를 움직여요.
4. Flyto2가 지도 위치를 직접 확인한 뒤에 완료로 판정해요.

---

## 개발자용

기능 목록, 안전 장치, 설정, 테스트 내용은 영어 버전에 있어요. [README.md → For developers](README.md#for-developers)

License: Apache-2.0 (`LICENSE`).
