.PHONY: lint-imports check-study-imports check help quickstart test test-unit prepare build-registry score weekly

## Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
	@echo ""
	@echo "Execution targets require FPL_DB_PATH or GW args."

lint-imports:
	lint-imports

check-study-imports:
	@result=$$(grep -rn "from studies\.\(lenses\|eda\|experiments\|synthesis\)" \
	  --include="*.py" \
	  --exclude-dir=studies \
	  --exclude-dir=tests \
	  --exclude-dir=.venv \
	  --exclude-dir=.git \
	  .); \
	if [ -n "$$result" ]; then \
	  echo "VIOLATION: forbidden study imports found outside studies/ and tests/:"; \
	  echo "$$result"; \
	  exit 1; \
	fi
	@echo "check-study-imports: PASSED"

check: lint-imports check-study-imports

## Verify DAL end-to-end against real DB (DB_PATH= arg or FPL_DB_PATH env var)
quickstart:
	python examples/quickstart.py $(DB_PATH)

## Run full test suite
test:
	pytest

## Run DB-free tests only (no live database required)
test-unit:
	pytest -m "not integration"

## Build analytical dataset: make prepare GW=36
prepare:
ifndef GW
	$(error GW is required: make prepare GW=36)
endif
	python -m dal.prepared.analytical_dataset \
	  --gw $(GW) \
	  --output-path outputs/prepared_gw$(GW).csv

## Build governed registry artifact: make build-registry GW=36
build-registry:
ifndef GW
	$(error GW is required: make build-registry GW=36)
endif
	python -m signals.registry.runner \
	  --gw $(GW) \
	  --source-registry-path studies/eda/findings/eda_03_joint_registry.csv \
	  --output-dir outputs/registry/gw$(GW)

## Score players for a gameweek: make score GW=36
score:
ifndef GW
	$(error GW is required: make score GW=36)
endif
	python -m intelligence.scoring.runner \
	  --gw $(GW) \
	  --db-path $(or $(FPL_DB_PATH),$(HOME)/.fpl/fpl.db) \
	  --output-dir outputs/scorer \
	  --registry-path outputs/registry/gw$(GW)/registry.csv

## Generate weekly signal intelligence: make weekly GW=36
weekly:
ifndef GW
	$(error GW is required: make weekly GW=36)
endif
	python -m intelligence.reporting.runner \
	  --gw $(GW) \
	  --registry-path outputs/registry/gw$(GW)/registry.csv
