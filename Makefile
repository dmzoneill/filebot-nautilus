.PHONY: all

all: push

SHELL := /bin/bash
CWD := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
version := $(shell grep 'version=.*' version | awk -F'=' '{print $$2}')
next := $(shell echo ${version} | awk -F. '/[0-9]+\./{$$NF++;print}' OFS=.)

install:
	mkdir -vp ~/.local/share/nautilus-python/extensions/
	ln -s $(CWD)/MediaInfoExt.py ~/.local/share/nautilus-python/extensions/MediaInfoExt.py
	ln -s $(CWD)/MediaInfoExtHelpers.py ~/.local/share/nautilus-python/extensions/MediaInfoExtHelpers.py
	ln -s $(CWD)/MediaInfoFileBot.py ~/.local/share/nautilus-python/extensions/MediaInfoFileBot.py

python-lint:
	black *.py

python:
	killall -9 nautilus
	nautilus	

bump:
	sed "s/$(version)/$(next)/" -i version

version: bump
	git add -A
	git commit -a -m "Bump to $(next)"

push: version
	git pull --rebase
	git push -u origin main:main -f

archive:
	tar -czvf archive.tgz *.py