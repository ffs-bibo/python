PYSCRIPTS:=sbasuche.py

suche: ./sbasuche.py
	uv run $(firstword $^) -vv

lint: $(PYSCRIPTS)
	ruff check $^

pretty: $(PYSCRIPTS)
	ruff format $^

all: lint pretty

.PHONY: suche all lint pretty
