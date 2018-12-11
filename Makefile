WORKSTATION_PKG ?= $(PULP_SDK_WS_INSTALL)

HEADER_FILES += $(shell find python -name *.py)


define declareInstallFile
$(INSTALL_DIR)/$(1): $(1)
	install -D $(1) $$@
INSTALL_HEADERS += $(INSTALL_DIR)/$(1)
endef


$(foreach file, $(HEADER_FILES), $(eval $(call declareInstallFile,$(file))))


sdk.clean:

sdk.header:

sdk.build: $(INSTALL_HEADERS)
	install -d $(WORKSTATION_PKG)/bin
	install -d $(WORKSTATION_PKG)/ref
	install -D bin/* $(WORKSTATION_PKG)/bin
	-gcc -O3 -o $(WORKSTATION_PKG)/bin/aes_encode aes/AesLib.c aes/main.c
