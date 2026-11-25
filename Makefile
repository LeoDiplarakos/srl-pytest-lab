TOPO = lab/srl-lab.clab.yml

.PHONY: deploy wait destroy lint format test test-disruptive test-all

deploy:
	sudo containerlab deploy -t $(TOPO)

wait:
	for i in $$(seq 1 40); do \
		echo "convergence check $$i/40"; \
		pytest tests/test_ospf.py tests/test_bgp.py -q --tb=no && exit 0; \
		sleep 10; \
	done; exit 1

destroy:
	sudo containerlab destroy -t $(TOPO) --cleanup

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	pytest

test-disruptive:
	pytest -m disruptive

test-all: test test-disruptive
