from __future__ import annotations

from fastapi.responses import HTMLResponse

from app_v2.app.main import app, root


def test_root_serves_ui_html():
    response = root()
    assert isinstance(response, HTMLResponse)
    html = response.body.decode("utf-8")
    assert "Analyse Essais DGA" in html
    assert "/static/app.js" in html
    assert "Rattacher les .dxd à la création" in html
    assert "Découverte DXD" not in html
    assert "Analyse active" not in html
    assert 'id="createAnalysisBtn"' in html
    assert "Analyse des canaux en cours" in html
    assert "Sauvegarder la structure" in html
    assert "Canaux DXD" in html
    assert "Sampling JSON" in html
    assert "Choix analyse" in html
    assert "Export JSON en cours" in html
    assert 'id="finalizeAnalysisBtn"' in html
    assert 'data-view="channels"' not in html
    assert 'data-view="resampling"' not in html
    assert "Fichiers avec anomalies" in html
    assert "Nombre max de fichiers" in html
    assert "Filtrer par nom de canal" in html
    assert 'id="explorationFileSelect"' in html
    assert 'id="explorationSignalPlot"' in html
    assert 'id="explorationTrajectoryPlot"' in html
    assert 'id="explorationTabs"' in html
    assert 'data-exploration-step="temporal"' in html
    assert 'data-exploration-step="parametric"' in html
    assert 'data-exploration-step="temporal-drift"' not in html
    assert "Vision temporelle par signal" in html
    assert "Vision paramétrique" in html
    assert "Drift temporel" not in html
    assert 'id="explorationDateFromInput"' in html
    assert 'id="explorationDateToInput"' in html
    assert 'id="explorationDateRangeStatus"' in html
    assert 'id="parametricScopeSelect"' in html
    assert 'id="parametricDateFromInput"' in html
    assert 'id="parametricDateToInput"' in html
    assert 'id="parametricFileControls"' in html
    assert 'id="parametricFileSelect"' in html
    assert 'id="parametricPrevBtn"' in html
    assert 'id="parametricNextBtn"' in html
    assert 'id="parametricChannelSelect"' in html
    assert 'id="parametricXChannelSelect"' not in html
    assert 'id="parametricYChannelSelect"' not in html
    assert 'id="parametricPlot"' in html
    assert "GET /api/analyses/{analysis_id}/exploration/signals/boxplot" not in html


def test_registered_routes_include_ui_and_current_api():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/" in paths
    assert "/api/status" in paths
    assert "/api/analyses" in paths
    assert "/api/analyses/{analysis_id}" in paths
    assert "/api/analyses/{analysis_id}/config" in paths
    assert "/api/analyses/{analysis_id}/files/discover-dxd" in paths
    assert "/api/analyses/{analysis_id}/channels/analyze" in paths
    assert "/api/analyses/{analysis_id}/channels/tasks/current" in paths
    assert "/api/analyses/{analysis_id}/channels/tasks/{task_id}" in paths
    assert "/api/analyses/{analysis_id}/channels/tasks/{task_id}/cancel" in paths
    assert "/api/analyses/{analysis_id}/channels/presence" in paths
    assert "/api/analyses/{analysis_id}/resampling/export-json" in paths
    assert "/api/analyses/{analysis_id}/resampling/tasks/current" in paths
    assert "/api/analyses/{analysis_id}/resampling/tasks/{task_id}" in paths
    assert "/api/analyses/{analysis_id}/resampling/tasks/{task_id}/cancel" in paths
    assert "/api/analyses/{analysis_id}/exploration/files" in paths
    assert "/api/analyses/{analysis_id}/exploration/labels" in paths
    assert "/api/analyses/{analysis_id}/exploration/date-range" in paths
    assert "/api/analyses/{analysis_id}/exploration/parametric" in paths
    assert "/api/analyses/{analysis_id}/exploration/files/{file_id}/signals/options" in paths
    assert "/api/analyses/{analysis_id}/exploration/files/{file_id}/series" in paths
    assert "/api/analyses/{analysis_id}/exploration/files/{file_id}/trajectory" in paths
