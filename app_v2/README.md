# MAS Essais App V2

Application v2 analyse-centrique. Cette version repart de zero : les `.dxd`
restent les acquisitions source, les `.json` restent les exports re-echantillonnes,
et SQLite est la source de verite pour tout le reste.

## Lancer en local

```bash
uvicorn app_v2.app.main:app --reload
```

## Tests

```bash
pytest app_v2/tests
```
