PYSCRIPTS:=sbasuche.py

suche: ./sbasuche.py
	$(firstword $^)

notebook: ./sbasuche-prototyp.ipynb
	uv run jupyter notebook $(firstword $^)

lint: $(PYSCRIPTS)
	ruff check $^

pretty: $(PYSCRIPTS)
	ruff format $^

all: lint pretty

.PHONY: suche all lint pretty notebook
