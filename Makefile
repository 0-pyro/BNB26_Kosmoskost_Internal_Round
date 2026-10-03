.PHONY: install test mock-server virtual-client proxy clean

install:
	python -m venv venv
	venv/Scripts/pip install pydantic fastapi websockets pytest

test:
	python -m pytest ws4_eval/tests/ -v

mock-server:
	python ws4_eval/mock_server.py

virtual-client:
	python ws4_eval/virtual_client.py

proxy:
	python ws4_eval/proxy.py

clean:
	rm -rf venv __pycache__ .pytest_cache
