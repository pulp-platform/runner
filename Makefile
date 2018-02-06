WORKSTATION_PKG ?= $(PULP_SDK_WS_INSTALL)

sdk.clean:

sdk.header:

sdk.build:
	install -d $(WORKSTATION_PKG)/bin
	install -d $(WORKSTATION_PKG)/ref
	install -d $(WORKSTATION_PKG)/python
	install -D bin/* $(WORKSTATION_PKG)/bin
	install -D python/* $(WORKSTATION_PKG)/python
	install -D ref/* $(WORKSTATION_PKG)/ref
	-gcc -O3 -o $(WORKSTATION_PKG)/bin/aes_encode aes/AesLib.c aes/main.c
