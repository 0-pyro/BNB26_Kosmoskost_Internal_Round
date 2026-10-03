.PHONY: install test test-client test-all smoke-test chaos-test eval demo server client clean

install:
	python -m venv venv
	venv/Scripts/pip install pydantic fastapi uvicorn websockets pytest pytest-asyncio numpy scipy jiwer pyroomacoustics httpx
	cd ws2_client && npm install

test:
	python -m pytest -v

test-client:
	cd ws2_client && npm test

test-all: test test-client

smoke-test:
	python tests/test_walking_skeleton_e2e.py 10

chaos-test:
	python tests/test_chaos_recovery.py

eval:
	python ws4_eval/eval_protocol.py

demo:
	python run_demo.py

server:
	python ws1_backend/main.py --port 8000

client:
	cd ws2_client && npm run dev

mock-server:
	python ws4_eval/mock_server.py

virtual-client:
	python ws4_eval/virtual_client.py

proxy:
	python ws4_eval/proxy.py

clean:
	rm -rf venv __pycache__ .pytest_cache ws2_client/dist ws2_client/node_modules/.vite
