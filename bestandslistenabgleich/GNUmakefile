PYSCRIPTS:=bestandslistenabgleich.py

abgleich: bestandslistenabgleich.py data/Bestandsliste_von_uns.csv
	./$(firstword $^) -v $(filter-out $(firstword $^),$^)

lint: $(PYSCRIPTS)
	ruff check $^

pretty: $(PYSCRIPTS)
	ruff format $^

all: lint pretty

.PHONY: abgleich all lint pretty
