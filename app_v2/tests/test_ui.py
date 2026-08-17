from __future__ import annotations

from fastapi.responses import HTMLResponse

from app_v2.app.main import app, root


def test_root_serves_ui_html():
    response = root()
    assert isinstance(response, HTMLResponse)
    html = response.body.decode("utf-8")
    assert "Analyse Essais DGA" in html
    assert "/static/app.js" in html
    assert 'id="loginView"' in html
    assert 'id="loginForm"' in html
    assert 'id="loginUserInput"' in html
    assert 'id="loginPasswordInput"' in html
    assert 'id="appShell"' in html
    assert "Rattacher les .dxd à la création" in html
    assert "Découverte DXD" not in html
    assert "Analyse active" not in html
    assert 'id="createAnalysisBtn"' in html
    assert "Analyse des canaux en cours" in html
    assert "Sauvegarder la structure de canaux" in html
    assert "Canaux DXD" in html
    assert "Indicateurs dynamiques" in html
    assert 'id="dynamicIndicatorsTable"' in html
    assert 'id="saveDynamicIndicatorsBtn"' in html
    assert "Sampling JSON" in html
    assert "Choisir une campagne" in html
    assert "Analyse dynamique" in html
    assert "Retournement" not in html
    assert 'data-view="models"' not in html
    assert 'id="view-models"' not in html
    assert "Modèles, poids et prédictions" not in html
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
    assert "Visualisation temporelle par signal" in html
    assert "Visualisation paramétrique" in html
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
    assert 'id="annotationFileSelect"' in html
    assert 'id="annotationTabs"' in html
    assert 'data-annotation-step="annotate"' in html
    assert 'data-annotation-step="catalog"' in html
    assert 'id="annotationChannelSelect"' in html
    assert 'id="annotationStartInput"' in html
    assert 'id="annotationLabelSelect"' in html
    assert 'id="annotationLabelInput"' not in html
    assert 'id="saveAnnotationBtn"' in html
    assert 'id="annotationSignalPlot"' in html
    assert 'id="annotationsTable"' in html
    assert 'id="annotationLabelSummaryTable"' in html
    assert 'id="annotationCatalogTable"' in html
    assert 'id="createAnnotationLabelBtn"' in html
    assert 'id="renameAnnotationLabelBtn"' in html
    assert 'id="dynamicAnalysisChannelChecklist"' in html
    assert 'id="dynamicAnalysisLabelChecklist"' in html
    assert 'id="dynamicAnalysisUserPromptInput"' not in html
    assert 'id="dynamicAnalysisChannelSelect"' not in html
    assert 'id="buildDynamicContextBtn"' not in html
    assert 'id="runDynamicAnalysisBtn"' in html
    assert 'id="dynamicGenerationAnnotationSelect"' in html
    assert 'id="dynamicGenerationPrevBtn"' in html
    assert 'id="dynamicGenerationNextBtn"' in html
    assert "Annotateur actif de segments" not in html
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
    assert "/api/analyses/{analysis_id}/annotation-sets" in paths
    assert "/api/analyses/{analysis_id}/annotations" in paths
    assert "/api/analyses/{analysis_id}/annotations/labels" in paths
    assert "/api/analyses/{analysis_id}/annotations/summary" in paths
    assert "/api/analyses/{analysis_id}/annotations/labels/{label}" in paths
    assert "/api/analyses/{analysis_id}/annotation-labels" in paths
    assert "/api/analyses/{analysis_id}/annotation-labels/{label_id}" in paths
    assert "/api/analyses/{analysis_id}/annotations/{annotation_id}" in paths
    assert "/api/analyses/{analysis_id}/annotations/{annotation_id}/versions" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/prompts" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/context" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/run" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/runs" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/runs/{run_id}" in paths
    assert "/api/analyses/{analysis_id}/dynamic-analysis/runs/{run_id}/versions" in paths
