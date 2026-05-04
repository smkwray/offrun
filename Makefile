PYTHON ?= $(HOME)/venvs/offrun/bin/python
RUFF ?= $(HOME)/venvs/offrun/bin/ruff
OFFRUN ?= $(HOME)/venvs/offrun/bin/offrun
SIBLING_ROOT ?= ..
FIXTURE_ROOT ?= tests/fixtures

.PHONY: test lint validate-config smoke-fixtures real-package clean-generated

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q

lint:
	$(RUFF) check .

validate-config:
	$(OFFRUN) validate-config

smoke-fixtures:
	PYTHONPATH=src $(PYTHON) -m offrun validate-config
	PYTHONPATH=src $(PYTHON) -m offrun validate-sibling-sources --sibling-root $(FIXTURE_ROOT)/sibling_root --strict
	PYTHONPATH=src $(PYTHON) -m offrun copy-sibling-outputs --sibling-root $(FIXTURE_ROOT)/sibling_root --overwrite
	PYTHONPATH=src $(PYTHON) -m offrun audit-trace-source-granularity --sibling-root $(FIXTURE_ROOT)/sibling_root
	PYTHONPATH=src $(PYTHON) -m offrun build-buyback-operations-panel --input $(FIXTURE_ROOT)/buybacks/buyback_operations_fixture.csv
	PYTHONPATH=src $(PYTHON) -m offrun build-liquidity-context-panel --trace-input $(FIXTURE_ROOT)/trace/trace_aggregate_fixture.csv --dealer-input $(FIXTURE_ROOT)/dealer/primary_dealer_fixture.csv
	PYTHONPATH=src $(PYTHON) -m offrun build-offrun-panel
	PYTHONPATH=src $(PYTHON) -m offrun write-offrun-report
	PYTHONPATH=src $(PYTHON) -m offrun write-output-manifest
	PYTHONPATH=src $(PYTHON) -m offrun validate-offrun-package --strict

real-package:
	PYTHONPATH=src $(PYTHON) -m offrun validate-config
	PYTHONPATH=src $(PYTHON) -m offrun validate-sibling-sources --sibling-root $(SIBLING_ROOT) --strict
	PYTHONPATH=src $(PYTHON) -m offrun prepare-real-inputs --sibling-root $(SIBLING_ROOT) --download-buybacks
	PYTHONPATH=src $(PYTHON) -m offrun download-finra-trace-aggregates --frequency daily
	PYTHONPATH=src $(PYTHON) -m offrun audit-trace-source-granularity --sibling-root $(SIBLING_ROOT)
	PYTHONPATH=src $(PYTHON) -m offrun build-buyback-operations-panel
	PYTHONPATH=src $(PYTHON) -m offrun build-liquidity-context-panel
	PYTHONPATH=src $(PYTHON) -m offrun build-offrun-panel
	PYTHONPATH=src $(PYTHON) -m offrun write-offrun-report
	PYTHONPATH=src $(PYTHON) -m offrun write-output-manifest
	PYTHONPATH=src $(PYTHON) -m offrun validate-offrun-package --strict

clean-generated:
	rm -rf data output .pytest_cache .ruff_cache src/offrun.egg-info
