.PHONY=default
default: |build test

.PHONY=FORCE
FORCE:

.PHONY=clean
clean: FORCE
	./run --clean

.PHONY=deps
deps: FORCE
	./run --deps

.PHONY=clean-all
clean-all: FORCE
	./run --clean-all

.PHONY=status
status: FORCE
	./run --status

.PHONY=build
build: FORCE
	./run --build

.PHONY=test
test: FORCE
	./run --test
