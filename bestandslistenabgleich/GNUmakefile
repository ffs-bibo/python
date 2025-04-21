PYSCRIPTS:=bestandslistenabgleich.py

abgleich: bestandslistenabgleich.py data/Bestandsliste_von_uns.csv
	uv run ./$(firstword $^) -vvv $(filter-out $(firstword $^),$^)

lint: $(PYSCRIPTS)
	ruff check $^

pretty: $(PYSCRIPTS)
	ruff format $^

all: lint pretty

clean: bestandslistenabgleich.py
	rm -f -- ./$(patsubst %.py,%.log,$(firstword $^))

Abgleich: clean abgleich

.PHONY: abgleich all lint pretty clean Abgleich
.NOTPARALLEL: Abgleich clean
