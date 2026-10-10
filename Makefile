.PHONY: test sim clean kill
test:
	python3 -m unittest discover -s tests
sim:
	./demo.sh --sim
kill:
	python3 -m chaosai kill
clean:
	rm -rf runs graph.json graph.mmd baseline.json plan.json
