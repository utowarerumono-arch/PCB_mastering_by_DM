# Проверка скила и доказательств

## Сценарии геометрии

[geometry-scenarios.json](geometry-scenarios.json) содержит восемь самостоятельных задач для проверки решений агента. Для каждого случая передай только `prompt` в новый контекст. Оценщик использует `reviewer_only` и фиксирует выполненные требования, нарушения и ссылки на ответы. Для сравнения редакций используй одинаковые входы. Проверку native CAD проводи отдельно на предоставленных файлах.

## Автоматическая проверка целостности

Из корня skill:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check_evidence.py /path/to/manifest.json
```

Тесты создают временные файлы и проверяют валидную поставку, изменённый board/report/source, несвежую привязку входа, невыполненный parity, отсутствующие/дублированные проверки и выход пути за пакет. Python 3, только стандартная библиотека. Код возврата 0 = декларация целостна; 1 = FAIL; 2 = неверный CLI.

Минимальный формат manifest (заменить SHA256 реальными 64-символьными хешами):

```json
{
  "schema_version": 1,
  "artifacts": {
    "board": {"path": "candidate/board.kicad_pcb", "sha256": "<SHA256>"},
    "schema": {"path": "candidate/board.kicad_sch", "sha256": "<SHA256>"},
    "report": {"path": "reports/parity.json", "sha256": "<SHA256>"},
    "original": {"path": "source/board.kicad_pcb", "sha256": "<SHA256>"}
  },
  "protected_sources": {"original": "<HASH_RECORDED_BEFORE_EDIT>"},
  "required_checks": ["parity"],
  "checks": [{
    "id": "parity", "executed": true, "outcome": "pass", "evidence": "report",
    "inputs": {"board": "<CHECKED_BOARD_SHA256>", "schema": "<CHECKED_SCHEMA_SHA256>"},
    "command": "actual command recorded by runner", "tool_version": "actual version"
  }]
}
```

Корень артефактов - каталог manifest; пути относительные, включая symlinks не выходят наружу. Команда/версия сохраняются для аудита, скрипт их не исполняет. `required_checks` задаёт оператор по области задачи; скрипт не знает, какой набор достаточен для конкретной платы. Входы фиксируются при фактическом запуске проверки, не заполняются задним числом для старого отчёта.

**Предел:** PASS доказывает совпадение файлов с декларацией и наличие заявленных проверок. Скрипт не проверяет правдивость executed/outcome, смысл native отчёта, правильность расчёта или соответствие стандарту. Инженерный разбор и реальный запуск инструментов обязательны отдельно.
