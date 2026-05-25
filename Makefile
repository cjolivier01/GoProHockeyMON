SHELL := /bin/bash

TOPDIR := $(shell pwd)
COMPILE_COMMANDS := compile_commands.json

PIO ?= pio
PIO_BIN := $(shell command -v $(PIO) 2>/dev/null)
PIO_SHEBANG := $(shell if [ -n "$(PIO_BIN)" ]; then sed -n '1s/^#!//p' "$(PIO_BIN)" 2>/dev/null; fi)
PIO_PYTHON ?= $(if $(PIO_SHEBANG),$(PIO_SHEBANG),python3)
ENV ?= esp32s3_amoled_ui
ACTIVE_ENVS ?= esp32dev esp32s3_radio esp32s3_amoled_ui ui_esp32dev_sim
DETECTED_PORT := $(shell $(PIO_PYTHON) "$(TOPDIR)/tools/find_esp32_port.py" 2>/dev/null)
PORT ?= $(DETECTED_PORT)
BAUD ?= 115200
PIO_ARGS ?=
MONITOR_ARGS ?= --echo
SERIAL_TIMEOUT ?= 4
SERIAL_QUIET_AFTER ?= 0.5
SERIAL_PRE_DRAIN ?= 1.5

define with_port
port="$(PORT)"; \
if [ -z "$$port" ]; then \
	printf 'No ESP32 serial port detected. Run "make ports" or set PORT=/dev/tty...\n' >&2; \
	exit 2; \
fi; \
printf 'Using port %s\n' "$$port"; \
$(1)
endef

all: print_targets

.PHONY: all print_targets bld build amoled upload monitor upload-monitor ports clean distclean erase check compiledb build-all radio sim ble-dump serial status connect rescan snapshot lower-double pair cancel FORCE

bld build amoled:
	$(PIO) run -e $(ENV) $(PIO_ARGS)

upload:
	@$(call with_port,exec $(PIO) run -e $(ENV) -t upload --upload-port "$$port" $(PIO_ARGS))

monitor:
	@$(call with_port,exec $(PIO) device monitor --port "$$port" --baud $(BAUD) $(MONITOR_ARGS))

upload-monitor: upload monitor

ports:
	$(PIO) device list
	@printf '\nPreferred ESP32 port: '
	@$(PIO_PYTHON) "$(TOPDIR)/tools/find_esp32_port.py" || printf '(none detected)\n'

clean:
	$(PIO) run -e $(ENV) -t clean

distclean:
	rm -rf "$(TOPDIR)/.pio/build/$(ENV)"

erase:
	@$(call with_port,exec $(PIO) run -e $(ENV) -t erase --upload-port "$$port" $(PIO_ARGS))

check:
	$(PIO) check -e $(ENV) $(PIO_ARGS)

compiledb: $(COMPILE_COMMANDS)

$(COMPILE_COMMANDS): FORCE
	$(PIO) run -e $(ENV) -t compiledb $(PIO_ARGS)
	@if [ ! -f "$(TOPDIR)/$(COMPILE_COMMANDS)" ]; then \
		db="$$(find "$(TOPDIR)/.pio/build/$(ENV)" -name compile_commands.json -print -quit)"; \
		if [ -n "$$db" ]; then \
			cp "$$db" "$(TOPDIR)/$(COMPILE_COMMANDS)"; \
		fi; \
	fi
	@test -f "$(TOPDIR)/$(COMPILE_COMMANDS)" || { printf 'Failed to generate %s in the project root.\n' "$(COMPILE_COMMANDS)" >&2; exit 1; }

build-all:
	$(PIO) run $(foreach env,$(ACTIVE_ENVS),-e $(env)) $(PIO_ARGS)

radio:
	$(PIO) run -e esp32s3_radio $(PIO_ARGS)

sim:
	$(PIO) run -e ui_esp32dev_sim $(PIO_ARGS)

ble-dump:
	$(PIO) run -e esp32s3_ble_cred_dump $(PIO_ARGS)

serial:
	@test -n "$(CMD)" || { printf 'Set CMD, for example: make serial CMD=status\n' >&2; exit 2; }
	@$(call with_port,exec $(PIO_PYTHON) "$(TOPDIR)/tools/serial_cmd.py" --port "$$port" --baud $(BAUD) --timeout "$(SERIAL_TIMEOUT)" --quiet-after "$(SERIAL_QUIET_AFTER)" --pre-drain "$(SERIAL_PRE_DRAIN)" "$(CMD)")

status:
	@$(MAKE) serial CMD=status

connect:
	@$(MAKE) serial CMD=connect SERIAL_TIMEOUT=20

rescan:
	@$(MAKE) serial CMD=rescan SERIAL_TIMEOUT=20

snapshot:
	@$(MAKE) serial CMD=snapshot SERIAL_TIMEOUT=30

lower-double:
	@$(MAKE) serial CMD="lower double" SERIAL_TIMEOUT=30

pair:
	@$(MAKE) serial CMD=pair SERIAL_TIMEOUT=35

cancel:
	@$(MAKE) serial CMD=cancel

print_targets:
	@printf '%s\n' \
		"Available make targets (run 'make <target>'):" \
		'' \
		'Primary ESP32-S3 AMOLED Workflow' \
		'--------------------------------' \
		'all             Show this help text (same as print_targets).' \
		'build           Build the selected PlatformIO environment.' \
		'bld             Alias for build.' \
		'amoled          Alias for build; defaults to the AMOLED UI firmware.' \
		'upload          Flash the selected environment to the board.' \
		'monitor         Open the serial monitor.' \
		'upload-monitor  Flash, then open the serial monitor.' \
		'ports           List PlatformIO-visible serial devices.' \
		'' \
		'Serial Test Commands' \
		'--------------------' \
		'status          Send the firmware status command and print the response.' \
		'connect         Ask firmware to connect to the saved GoPro.' \
		'rescan          Retry saved-camera BLE/Wi-Fi connection.' \
		'snapshot        Run the snapshot path over serial.' \
		'lower-double    Simulate the lower side-button double click.' \
		'pair            Start Pair New over serial.' \
		'cancel          Cancel current pairing/connection action.' \
		'serial          Send an arbitrary command: make serial CMD="page maintenance".' \
		'' \
		'Maintenance' \
		'-----------' \
		'clean           Run PlatformIO clean for ENV.' \
		'distclean       Remove .pio/build/ENV for a fresh local rebuild.' \
		'erase           Erase flash on the selected board.' \
		'check           Run PlatformIO static checks for ENV.' \
		'compile_commands.json  Generate root compile database for clangd.' \
		'compiledb       Alias for compile_commands.json.' \
		'' \
		'Other Configured Environments' \
		'-----------------------------' \
		'build-all       Build active firmware environments.' \
		'radio           Build esp32s3_radio.' \
		'sim             Build ui_esp32dev_sim.' \
		'ble-dump        Build esp32s3_ble_cred_dump.' \
		'' \
		'Variables' \
		'---------' \
		'ENV             PlatformIO environment (default: esp32s3_amoled_ui).' \
		'ACTIVE_ENVS     Environments used by build-all.' \
		'PORT            Serial/upload port; auto-detected when unset.' \
		'BAUD            Monitor/serial baud rate (default: 115200).' \
		'PIO             PlatformIO executable (default: pio).' \
		'PIO_PYTHON      Python command with pyserial; inferred from the pio executable when unset.' \
		'PIO_ARGS        Extra arguments passed to pio run/check commands.' \
		'MONITOR_ARGS    Extra pio device monitor arguments (default: --echo).' \
		'SERIAL_TIMEOUT  Seconds to read after one-shot serial commands.' \
		'SERIAL_QUIET_AFTER  Stop one-shot serial reads after this many quiet seconds.' \
		'SERIAL_PRE_DRAIN    Drain existing serial logs for this many seconds before sending.'
