.PHONY: demo demo-down test

demo:
	docker compose up --build threadwise-demo

demo-down:
	docker compose down

test:
	python3 -m unittest discover -s tests
	python3 scripts/check_public_data_hygiene.py
