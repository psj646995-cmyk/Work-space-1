from ..xg_estimate import estimate_shot_xg


def test_closer_shot_has_higher_xg_than_farther_shot_at_same_angle():
    goal_a, goal_b = (480.0, 0.0), (520.0, 0.0)
    close_shot = (500.0, 50.0)
    far_shot = (500.0, 500.0)

    close_xg = estimate_shot_xg(close_shot, goal_a, goal_b, frame_diagonal=1000.0)
    far_xg = estimate_shot_xg(far_shot, goal_a, goal_b, frame_diagonal=1000.0)

    assert close_xg > far_xg


def test_wider_angle_has_higher_xg_than_narrow_angle_at_same_distance():
    frame_diagonal = 1000.0
    narrow_goal_a, narrow_goal_b = (498.0, 0.0), (502.0, 0.0)
    wide_goal_a, wide_goal_b = (300.0, 0.0), (700.0, 0.0)
    shot_position = (500.0, 200.0)

    narrow_xg = estimate_shot_xg(shot_position, narrow_goal_a, narrow_goal_b, frame_diagonal)
    wide_xg = estimate_shot_xg(shot_position, wide_goal_a, wide_goal_b, frame_diagonal)

    assert wide_xg > narrow_xg


def test_xg_always_between_zero_and_one():
    xg = estimate_shot_xg((0.0, 0.0), (10.0, 10.0), (20.0, 20.0), frame_diagonal=1000.0)
    assert 0.0 <= xg <= 1.0


def test_degenerate_goal_points_do_not_crash():
    # 슈팅 지점이 골대 기둥과 정확히 같은 좌표인 극단적 경우
    xg = estimate_shot_xg((10.0, 10.0), (10.0, 10.0), (20.0, 20.0), frame_diagonal=1000.0)
    assert 0.0 <= xg <= 1.0
