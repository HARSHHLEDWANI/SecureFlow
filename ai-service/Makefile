install:
	pip install -r requirements.txt

train:
	python app/train.py

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/ -v
