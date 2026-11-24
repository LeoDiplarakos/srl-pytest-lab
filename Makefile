TOPO = lab/srl-lab.clab.yml

.PHONY: deploy destroy lint format test test-disruptive test-all

deploy:
	sudo containerlab deploy -t $(TOPO)

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
