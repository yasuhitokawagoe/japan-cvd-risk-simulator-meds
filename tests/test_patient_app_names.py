import app_streamlit_patient as patient_app


def test_plotly_graph_objects_alias_is_not_shadowed():
    assert hasattr(patient_app.go, "Figure")
    assert callable(patient_app.navigate_to)


def test_tablet_comparison_chart_keeps_labels_and_values_visible():
    labels = ["心筋梗塞", "脳卒中", "すべての原因による死亡"]
    figure = patient_app.build_comparison_figure(labels, [1.0, 5.6, 18.3], [0.9, 4.5, 13.1])
    assert figure.layout.margin.l >= 190
    assert figure.layout.margin.r >= 90
    assert figure.layout.xaxis.range[1] > 18.3
    assert all(trace.cliponaxis is False for trace in figure.data)


def test_body_defaults_follow_selected_sex(monkeypatch):
    monkeypatch.setitem(patient_app.st.session_state, "p_sex", "male")
    patient_app.set_body_defaults_for_selected_sex()
    assert patient_app.st.session_state["p_height"] == 170
    assert patient_app.st.session_state["p_weight"] == 65

    monkeypatch.setitem(patient_app.st.session_state, "p_sex", "female")
    patient_app.set_body_defaults_for_selected_sex()
    assert patient_app.st.session_state["p_height"] == 160
    assert patient_app.st.session_state["p_weight"] == 55
