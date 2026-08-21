import app_streamlit_patient as patient_app


def test_plotly_graph_objects_alias_is_not_shadowed():
    assert hasattr(patient_app.go, "Figure")
    assert callable(patient_app.navigate_to)
