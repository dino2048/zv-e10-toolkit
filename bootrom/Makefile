PYTHON ?= python3
export PYTHON

.PHONY: all build check test clean
all: build

build:
	$(MAKE) -C stage1
	$(MAKE) -C stage2

check:
	$(PYTHON) -B tools/check_abi.py

test: check
	$(MAKE) -C stage2 test

clean:
	$(MAKE) -C stage1 clean
	$(MAKE) -C stage2 clean
