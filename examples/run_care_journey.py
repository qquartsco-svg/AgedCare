"""AgedCare_Stack 전체 여정 시뮬레이션.

시나리오:
  [집] AI펫 케어 → [휠체어] 자율이동 → [자동차] 자율주행 →
  [휠체어] 병원 내 이동 → [자동차] 귀가 주행 → [휠체어] 귀가 이동 → [집] AI펫 복귀

실행:
  python examples/run_care_journey.py
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

from aged_care import (
    CareAgent, CareProfile, CareContext, PlatformType,
    VitalSigns, EnvironmentFrame, AgentMemory, MedicalInfo,
)


def print_step(step, ctx, decision):
    platform_emoji = {
        "pet": "🐾", "wheelchair": "♿", "car": "🚗", "none": "⏳"
    }
    emoji = platform_emoji.get(ctx.platform.value, "?")
    speak = f'💬 "{decision.speak}"' if decision.speak else ""
    alert = f'🚨 {decision.alert}' if decision.alert else ""
    hoff  = f'→ {decision.request_handoff.value}' if decision.request_handoff else ""
    print(f"  [{step:4d}] {emoji} {ctx.platform.value:12s} | "
          f"action={decision.action:20s} {hoff} {speak} {alert}")


def main():
    print("=" * 70)
    print("AgedCare_Stack — AI 케어 여정 시뮬레이션")
    print("=" * 70)

    # ── 케어 대상자 프로파일 ──────────────────────────────────────
    profile = CareProfile(
        person_id="GNJz-001",
        name="홍길동",
        age=78,
        medical=MedicalInfo(
            conditions=("고혈압", "당뇨"),
            medications=("메트포르민", "아스피린"),
            mobility_level=0.6,
            fall_risk=0.4,
        ),
        home_location=(0.0, 0.0),
        emergency_contacts=("010-1234-5678",),
    )

    agent = CareAgent(profile)
    ctx   = agent.start_session()
    ctx.vitals = VitalSigns(heart_rate_bpm=72, spo2_pct=97, body_temp_c=36.4)

    # ─────────────────────────────────────────────────────────────
    # 1단계: 집 — AI 펫 케어 (50 틱)
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("🐾 1단계: 집 — AI 펫 케어")
    print(f"{'─'*60}")
    for step in range(50):
        if step == 40:
            ctx.extra["go_out"] = True
            ctx.destination = (500.0, 200.0)   # 병원 위치
            log.info("외출 신호 발생 → 병원 행")
        ctx, decision = agent.tick(ctx)
        if step % 10 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.WHEELCHAIR:
            log.info("휠체어 핸드오프 요청 감지")
            agent.execute_handoff(ctx)
            ctx.extra.pop("go_out", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 2단계: 휠체어 — 집 → 자동차 위치
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("♿ 2단계: 휠체어 — 집 → 자동차 승차 위치")
    print(f"{'─'*60}")
    for step in range(50, 120):
        if step == 110:
            ctx.extra["car_ready"] = True
            log.info("자동차 도착 — 승차 준비")
        ctx, decision = agent.tick(ctx)
        if step % 15 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.CAR:
            log.info("자동차 핸드오프 요청 감지")
            agent.execute_handoff(ctx)
            ctx.extra.pop("car_ready", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 3단계: 자동차 — 자율주행 (병원까지)
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("🚗 3단계: 자동차 — 자율주행 (목적지까지)")
    print(f"{'─'*60}")
    for step in range(120, 220):
        if step == 210:
            ctx.extra["arrived"] = True
            log.info("목적지 도착")
        ctx, decision = agent.tick(ctx)
        if step % 20 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.WHEELCHAIR:
            log.info("휠체어 핸드오프 요청 (하차)")
            agent.execute_handoff(ctx)
            ctx.extra.pop("arrived", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 4단계: 휠체어 — 목적지 내 이동 후 귀가
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("♿ 4단계: 목적지 이동 후 귀가 자동차 승차")
    print(f"{'─'*60}")
    ctx.destination = profile.home_location   # 귀가
    for step in range(220, 300):
        if step == 290:
            ctx.extra["car_ready"] = True
        ctx, decision = agent.tick(ctx)
        if step % 15 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.CAR:
            agent.execute_handoff(ctx)
            ctx.extra.pop("car_ready", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 5단계: 자동차 — 귀가 자율주행
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("🚗 5단계: 자동차 — 귀가 자율주행")
    print(f"{'─'*60}")
    for step in range(300, 380):
        if step == 370:
            ctx.extra["arrived"] = True
        ctx, decision = agent.tick(ctx)
        if step % 20 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.WHEELCHAIR:
            agent.execute_handoff(ctx)
            ctx.extra.pop("arrived", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 6단계: 휠체어 — 집 도착 → AI 펫 복귀
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("♿ 6단계: 휠체어 — 집 진입 → AI 펫 복귀")
    print(f"{'─'*60}")
    ctx.destination = None
    for step in range(380, 430):
        if step == 420:
            ctx.extra["at_home"] = True
        ctx, decision = agent.tick(ctx)
        if step % 10 == 0 or decision.request_handoff:
            print_step(step, ctx, decision)
        if decision.request_handoff == PlatformType.PET:
            log.info("AI 펫 복귀 핸드오프")
            agent.execute_handoff(ctx)
            ctx.extra.pop("at_home", None)
            break

    # ─────────────────────────────────────────────────────────────
    # 7단계: 집 — AI 펫 복귀 케어
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("🐾 7단계: 집 귀환 — AI 펫 복귀 케어")
    print(f"{'─'*60}")
    for step in range(430, 480):
        ctx, decision = agent.tick(ctx)
        if step % 10 == 0:
            print_step(step, ctx, decision)

    # ─────────────────────────────────────────────────────────────
    # 최종 요약
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("최종 케어 요약")
    print(f"{'=' * 70}")
    print(agent.summary())
    print(f"\n  오늘의 알림:")
    for a in agent.memory.alerts_today[-5:]:
        print(f"    - {a}")
    print(f"\n  마지막 대화:")
    for c in agent.memory.conversation_history[-3:]:
        print(f"    {c}")


if __name__ == "__main__":
    main()
