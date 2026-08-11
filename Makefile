.PHONY: demo demo-down prototype-ui test

demo:
	docker compose up --build threadwise-demo

demo-down:
	docker compose down

prototype-ui:
	python3 -m http.server 8892 --bind 127.0.0.1

test:
	python3 -m unittest discover -s tests
	python3 scripts/check_public_data_hygiene.py
