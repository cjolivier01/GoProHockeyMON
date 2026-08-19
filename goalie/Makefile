BLENDER ?= $(shell command -v blender 2>/dev/null || printf '%s' /home/colivier/Apps/Blender/blender)
BLENDER_FLAGS ?= --background --factory-startup --python-exit-code 1
OUTPUT_DIR ?= goalie_output
VALIDATE_OUTPUT_DIR ?= $(OUTPUT_DIR)_validate
STATURE_MM ?= 1880

.DEFAULT_GOAL := build

.PHONY: build validate clean

build:
	$(BLENDER) $(BLENDER_FLAGS) --python hockey_goalie_mannequin_blender.py -- \
		--output-dir $(OUTPUT_DIR) --stature-mm $(STATURE_MM)

validate:
	$(BLENDER) $(BLENDER_FLAGS) --python hockey_goalie_mannequin_blender.py -- \
		--output-dir $(VALIDATE_OUTPUT_DIR) --stature-mm $(STATURE_MM) --no-export --no-save-blend

clean:
	@printf '%s\n' "Generated files are under $(OUTPUT_DIR). Remove that directory explicitly when desired."
