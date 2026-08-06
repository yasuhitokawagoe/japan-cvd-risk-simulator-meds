from pathlib import Path


APP_SOURCE = (Path(__file__).resolve().parents[1] / "app_streamlit_outcomes.py").read_text(
    encoding="utf-8"
)


def test_risk_calculation_is_not_triggered_automatically():
    assert "should_auto_calculate" not in APP_SOURCE
    assert "if not backcast_enabled and manual_button_clicked:" in APP_SOURCE


def test_backcast_requires_its_calculation_button():
    assert '"🔄 反実仮想を計算"' in APP_SOURCE
    assert "backcast_enabled and backcast_keys and backcast_ready" in APP_SOURCE


def test_calculation_button_is_rendered_in_sidebar_slot():
    assert "calculation_button_slot = st.empty()" in APP_SOURCE
    assert "calculation_button_slot.button(" in APP_SOURCE


def test_outcomes_engine_is_cached_across_widget_reruns():
    assert "@st.cache_resource(show_spinner=False)" in APP_SOURCE
    assert 'engine = _cached_outcomes_engine("config.yaml")' in APP_SOURCE


def test_backcast_does_not_render_adjustment_picker_twice():
    assert 'elif mode == "adjust":' in APP_SOURCE
    assert 'key="backcast_calculate_main"' in APP_SOURCE
    assert 'key="backcast_calculate_sidebar"' in APP_SOURCE
