PYSCRIPTS:=bestandslistenabgleich.py

abgleich: bestandslistenabgleich.py data/Bestandsliste_von_SBA.csv data/Bestandsliste_von_uns.csv
	python3 $(firstword $^) $(filter-out $(firstword $^),$^)

lint: $(PYSCRIPTS)
	flake8 $^

pretty: black

prerequisites: requirements.txt install-python-prerequisites.sh
	./install-python-prerequisites.sh

black: $(PYSCRIPTS)
	$@ $^

vulture: $(PYSCRIPTS)
	$@ $^

all: black lint vulture

.PHONY: abgleich all black lint pretty prerequisites vulture
