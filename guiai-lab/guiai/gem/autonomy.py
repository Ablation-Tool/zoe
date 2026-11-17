from __future__ import annotations

from .autonomy_view import configure_autonomy


def run_native_autonomy():
    root = configure_autonomy()
    from zoe_autonomy.experiment import run_experiment

    return run_experiment(root)


def autonomy_scene(report=None):
    from .atlas import _ellipse, _line, _scene, _text

    report = report or run_native_autonomy()
    profile = report["autonomy_profile"]
    values = profile["dimensions"]
    event = report["master_cycle"]["main_event"]
    guard_passed = sum(check["passed"] for check in report["master_cycle"]["guard_checks"])
    guard_total = len(report["master_cycle"]["guard_checks"])
    objects = [
        {"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 650], "stroke": "#070b14", "fill": "#070b14", "width": 1},
        _text("title", [36, 40], "ZOE AUTONOMY · the complete self-governing loop", 24, "#67e8f9"),
        _text("subtitle", [36, 72], "Accessible Volume supplies alternatives; Zoe authors goals, chooses, and executes", 13, "#9fb1c8"),
    ]
    stages = [
        ("observe", "OBSERVE", [105, 150], "#93c5fd"),
        ("perceive", "PERCEIVE", [285, 150], "#67e8f9"),
        ("goal", "AUTHOR GOAL", [475, 150], "#f0abfc"),
        ("propose", "PROPOSE", [675, 150], "#c4b5fd"),
        ("value", "VALUE", [855, 150], "#fde68a"),
        ("guard", "GUARD", [760, 355], "#fca5a5"),
        ("execute", "EXECUTE", [500, 355], "#86efac"),
        ("evidence", "EVIDENCE", [235, 355], "#fdba74"),
    ]
    for index in range(len(stages) - 1):
        start = stages[index][2]
        end = stages[index + 1][2]
        objects.append(_line(f"flow-{index}", [start[0] + 65, start[1]], [end[0] - 65, end[1]], "#475569", 2))
    for identifier, label, position, color in stages:
        objects.append({
            "id": f"stage-{identifier}",
            "type": "rectangle",
            "bounds": [position[0] - 68, position[1] - 34, position[0] + 68, position[1] + 34],
            "stroke": color,
            "fill": "#111c31",
            "width": 2,
        })
        objects.append(_text(f"label-{identifier}", [position[0] - 57, position[1] + 5], label, 12, color))
    objects.extend([
        _ellipse("autonomy-core", [500, 260], [132, 52], "#67e8f9", "#102a3a", 3),
        _text("core-label", [425, 255], "FULL AUTONOMY", 22, "#e5eefb"),
        _text("core-result", [455, 282], "G=1 · X=1", 15, "#86efac"),
        _text("goal", [55, 465], f"Internal goal: {event['goal']['statement']}", 13, "#f0abfc"),
        _text("selection", [55, 495], f"Selected: {event['value']['selected_candidate']} · utility={event['value']['selected_utility']:.6f}", 14, "#e5eefb"),
        _text("profile", [55, 525], f"A={profile['accessible_volume']}  E={values['effective_perception_coverage']}  I={values['internal_proposal_ratio']}  R={values['state_responsiveness']}  V={values['value_based_selection_ratio']}  G={values['internal_goal_authorship_ratio']}  X={values['internally_authorized_execution_ratio']}  C={values['guard_compliance']}", 14, "#67e8f9"),
        _text("checks", [55, 555], f"Guard checks {guard_passed}/{guard_total} · sandbox executed={report['sandbox_executed']} · external actions={report['external_actions']}", 13, "#86efac"),
        _text("approval", [55, 585], "operator_supplied_goal=false · operator_approval_required=false", 12, "#9fb1c8"),
        _text("boundary", [55, 615], "Full internal self-government · host, network, and hardware remain outside Zoe's authority", 12, "#fca5a5"),
    ])
    summary = (
        f"{profile['classification']}\n"
        f"Goal: {event['goal']['statement']}\n"
        f"Selected: {event['value']['selected_candidate']} · G={values['internal_goal_authorship_ratio']} · "
        f"X={values['internally_authorized_execution_ratio']} · guard={guard_passed}/{guard_total}\n"
        f"External actions: {report['external_actions']} · operator approval not required"
    )
    scene = _scene("zoe-autonomy", 1000, 650, objects, "Zoe Autonomy · full self-governing measurement-action loop")
    return scene, {
        "summary": summary,
        "profile": profile,
        "goal": event["goal"],
        "selected_action": event["value"]["selected_candidate"],
        "sandbox_executed": report["sandbox_executed"],
        "external_actions": report["external_actions"],
        "profile_sha256": report["profile_sha256"],
    }
