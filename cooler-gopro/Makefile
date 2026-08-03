BLENDER ?= $(shell command -v blender 2>/dev/null || command -v /home/colivier/Apps/Blender/blender 2>/dev/null || printf '%s' blender)
BLENDER_FLAGS ?= --background --factory-startup
PDF_PYTHON ?= $(shell command -v /home/colivier/miniforge3/bin/python 2>/dev/null || command -v python3 2>/dev/null || printf '%s' python3)

DIMENSION_PDF := hockeymom_3_cam_cover_configuration_dimensions.pdf
FAN_CASE_DIMENSION_PDF := gopro_fan_case_configuration_dimensions.pdf

FLAT_FAN_COVER_STLS := flat-fan-cover.stl
WRAPPING_FAN_COVER_STLS := wrapping-fan-cover.stl
HORN_STLS := horn_parametric_blender.stl
MISSION1_DUMMY_STLS := gopro_mission1_dummy_recreated.stl
DUAL_FAN_STLS := \
	gopro_dual_fan_parametric.stl \
	gopro_dual_fan_adapter.stl
FAN_SILENCER_SIZE ?= 40
FAN_SILENCER_SUPPORTED_SIZES := 40 60 80 120
ifeq ($(filter $(FAN_SILENCER_SIZE),$(FAN_SILENCER_SUPPORTED_SIZES)),)
$(error FAN_SILENCER_SIZE must be one of: $(FAN_SILENCER_SUPPORTED_SIZES))
endif
FAN_SILENCER_PREFIX := gopro_$(FAN_SILENCER_SIZE)mm_fan_silencer
FAN_SILENCER_STL_SUFFIXES := \
	.stl \
	_flange.stl \
	_spacer.stl \
	_curved_baffle.stl \
	_center_baffle.stl \
	_alignment_sleeve.stl
FAN_SILENCER_SOURCE_DEPS := gopro_fan_silencer_parametric_blender.py fan_size_presets.py
ifeq ($(FAN_SILENCER_SIZE),40)
FAN_SILENCER_SOURCE_DEPS += gopro_fan_case_parametric_blender.py
endif
FAN_SILENCER_STLS := \
	$(foreach suffix,$(FAN_SILENCER_STL_SUFFIXES),$(FAN_SILENCER_PREFIX)$(suffix))
FAN_SILENCER_KNOWN_STLS := $(foreach size,$(FAN_SILENCER_SUPPORTED_SIZES),\
	$(foreach suffix,$(FAN_SILENCER_STL_SUFFIXES),gopro_$(size)mm_fan_silencer$(suffix)))
FAN_SILENCER_OBSOLETE_STLS := gopro_40mm_fan_silencer_core_half.stl
BAFFLE_CARTRIDGE_ENABLED := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('gopro_fan_case_parametric_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'BAFFLE_CARTRIDGE_ENABLED' for target in node.targets)))")
BAFFLE_CARTRIDGE_MATERIAL_MODE := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('gopro_fan_case_parametric_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'BAFFLE_CARTRIDGE_MATERIAL_MODE' for target in node.targets)))")
FAN_CASE_CORE_STLS := \
	gopro_fan_case_parametric.stl \
	gopro_fan_case_back.stl \
	gopro_fan_case_insert.stl \
	gopro_fan_case_button.stl \
	gopro_fan_case_front_retainer.stl \
	gopro_fan_case_rotating_keeper.stl
FAN_CASE_BAFFLE_BODY_STLS := \
	gopro_fan_case_baffle_tray.stl \
	gopro_fan_case_baffle_lid.stl
FAN_CASE_BAFFLE_GASKET_STLS := gopro_fan_case_baffle_gasket.stl
FAN_CASE_BAFFLE_STLS := $(FAN_CASE_BAFFLE_BODY_STLS) $(FAN_CASE_BAFFLE_GASKET_STLS)
ifeq ($(BAFFLE_CARTRIDGE_ENABLED),True)
FAN_CASE_ACTIVE_BAFFLE_STLS := $(FAN_CASE_BAFFLE_BODY_STLS)
ifeq ($(BAFFLE_CARTRIDGE_MATERIAL_MODE),RIGID)
FAN_CASE_ACTIVE_BAFFLE_STLS += $(FAN_CASE_BAFFLE_GASKET_STLS)
endif
endif
FAN_CASE_STLS := $(FAN_CASE_CORE_STLS) $(FAN_CASE_ACTIVE_BAFFLE_STLS)
FAN_CASE_ALL_STLS := $(FAN_CASE_CORE_STLS) $(FAN_CASE_BAFFLE_STLS)
HOCKEYMOM_COVER_STLS := \
	hockeymom_3_cam_cover_original_style_base.stl \
	hockeymom_3_cam_cover_original_style_lid.stl \
	hockeymom_3_cam_cover_camera_bracket_1.stl \
	hockeymom_3_cam_cover_camera_bracket_2.stl \
	hockeymom_3_cam_cover_rotating_camera_cartridge.stl \
	hockeymom_3_cam_cover_idler_shaft_cap.stl \
	hockeymom_3_cam_cover_worm_inner_bearing_cap.stl \
	hockeymom_3_cam_cover_worm_outer_bearing_cap.stl \
	hockeymom_3_cam_cover_fan_acoustic_trough.stl \
	hockeymom_3_cam_cover_fan_acoustic_lid.stl \
	hockeymom_3_cam_cover_fan_acoustic_boot_seal_1.stl \
	hockeymom_3_cam_cover_fan_acoustic_boot_seal_2.stl

# These are emitted only when their corresponding reference/service export
# switches are enabled.  Keep them out of the grouped build prerequisites,
# but include them in cleanup so stale optional artifacts cannot survive a
# configuration change.
HOCKEYMOM_OPTIONAL_STLS := \
	hockeymom_3_cam_cover_ASSEMBLY_REFERENCE_NOT_FOR_PRINT.stl \
	hockeymom_3_cam_cover_cartridge_removable_front_stop.stl \
	hockeymom_3_cam_cover_purchased_worm_reference.stl \
	hockeymom_3_cam_cover_purchased_worm_wheel_reference.stl \
	hockeymom_3_cam_cover_purchased_4mm_idler_shaft_reference.stl \
	hockeymom_3_cam_cover_idler_spur_pinion.stl \
	hockeymom_3_cam_cover_fan_gasket_1.stl \
	hockeymom_3_cam_cover_fan_gasket_2.stl

STL_FILES := \
	$(FLAT_FAN_COVER_STLS) \
	$(WRAPPING_FAN_COVER_STLS) \
	$(HORN_STLS) \
	$(MISSION1_DUMMY_STLS) \
	$(DUAL_FAN_STLS) \
	$(FAN_SILENCER_STLS) \
	$(FAN_CASE_STLS)

.DEFAULT_GOAL := print_targets
.DELETE_ON_ERROR:

.PHONY: \
	all print_targets dim-pdf check-dim-pdf-sync \
	fan-case-dim-pdf check-fan-case-dim-pdf-sync \
	flat-fan-cover wrapping-fan-cover horn mission1-dummy dual-fan fan-silencer fan-case hockeymom-cover \
	clean clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-silencer clean-fan-case clean-hockeymom-cover \
	clean-dim-pdf clean-fan-case-dim-pdf

# Keep the generated dimension guide synchronized with both model sources.
# The PDF target below also depends on its generator, so any configuration or
# documentation-layout change is reflected by the next normal `make all`.
all: $(STL_FILES) $(HOCKEYMOM_COVER_STLS) \
	$(DIMENSION_PDF) $(FAN_CASE_DIMENSION_PDF) \
	check-dim-pdf-sync check-fan-case-dim-pdf-sync

print_targets:
	@printf '%s\n' \
		"Available make targets (run 'make <target>'):" \
		'' \
		'STL Builds' \
		'----------' \
		'all                       Build all STL files and synchronized dimension PDF.' \
		'flat-fan-cover            Build the flat fan cover STL.' \
		'wrapping-fan-cover        Build the wrapping fan cover STL.' \
		'horn                      Build the parametric horn STL.' \
		'mission1-dummy            Build the recreated GoPro Mission 1 dummy STL.' \
		'dual-fan                  Build the parametric dual-fan STL.' \
		'fan-silencer              Build a fan silencer; set FAN_SILENCER_SIZE=40/60/80/120.' \
		'fan-case                  Build the case, buttons, baffle tray/lid/seal, swing gate, and keeper STLs.' \
		'hockeymom-cover           Build all HOCKEYMOM 3 camera-cover component STLs.' \
		'' \
		'Documentation' \
		'-------------' \
		'dim-pdf                   Build the HOCKEYMOM 3 configuration dimension PDF.' \
		'check-dim-pdf-sync        Verify the PDF matches its model and generator sources.' \
		'fan-case-dim-pdf          Build the fan-case configuration dimension PDF.' \
		'check-fan-case-dim-pdf-sync  Verify PDF synchronization and engineering-drawing coverage.' \
		'' \
		'Cleanup' \
		'-------' \
		'clean                     Remove all generated STL and dimension-PDF files.' \
		'clean-flat-fan-cover      Remove the flat fan cover STL.' \
		'clean-wrapping-fan-cover  Remove the wrapping fan cover STL.' \
		'clean-horn                Remove the parametric horn STL.' \
		'clean-mission1-dummy      Remove the Mission 1 dummy STL.' \
		'clean-dual-fan            Remove the dual-fan STL.' \
		'clean-fan-silencer        Remove generated 40/60/80/120 mm fan silencer STLs.' \
		'clean-fan-case            Remove all fan-case STLs.' \
		'clean-hockeymom-cover     Remove all HOCKEYMOM 3 camera-cover STLs.' \
		'clean-dim-pdf             Remove the HOCKEYMOM 3 configuration dimension PDF.' \
		'clean-fan-case-dim-pdf    Remove the fan-case configuration dimension PDF.' \
		'' \
		'Meta' \
		'----' \
		'print_targets             Show this help text.'

flat-fan-cover: $(FLAT_FAN_COVER_STLS)
wrapping-fan-cover: $(WRAPPING_FAN_COVER_STLS)
horn: $(HORN_STLS)
mission1-dummy: $(MISSION1_DUMMY_STLS)
dual-fan: $(DUAL_FAN_STLS)
fan-silencer: $(FAN_SILENCER_STLS)
fan-case: $(FAN_CASE_STLS)
dim-pdf: $(DIMENSION_PDF)
fan-case-dim-pdf: $(FAN_CASE_DIMENSION_PDF)

check-dim-pdf-sync: $(DIMENSION_PDF)
	$(PDF_PYTHON) generate_hockeymom_config_dimension_pdf.py --check-sync

check-fan-case-dim-pdf-sync: $(FAN_CASE_DIMENSION_PDF)
	$(PDF_PYTHON) generate_fan_case_config_dimension_pdf.py --check-sync

$(DIMENSION_PDF): generate_hockeymom_config_dimension_pdf.py \
	hockeymom_3_cam_cover_original_style_blender.py gopro_mission1_dummy_blender.py
	$(PDF_PYTHON) $<

$(FAN_CASE_DIMENSION_PDF): generate_fan_case_config_dimension_pdf.py \
	gopro_fan_case_parametric_blender.py $(FAN_CASE_STLS)
	$(PDF_PYTHON) $<

# Load a generator without triggering its __main__ block, build its selected
# object, and export that selection. These two scripts intentionally do not
# contain their own STL-export option.
define export_selected_object
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import bpy, os; p='$(1)'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); obj=ns['$(2)'](); ns['select_only'](obj); out=os.path.abspath('$@'); (bpy.ops.wm.stl_export(filepath=out,export_selected_objects=True) if hasattr(bpy.ops.wm,'stl_export') else bpy.ops.export_mesh.stl(filepath=out,use_selection=True))"
endef

# Load a generator, override its disabled export flag and output path, then
# call its normal build entry point.
define run_single_output_generator
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$(1)'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['$(3)']='$@'; ns['$(2)']()"
endef

$(FLAT_FAN_COVER_STLS): flat-fan-cover.py
	$(call export_selected_object,$<,build_flat_fan_cover)

$(WRAPPING_FAN_COVER_STLS): wrapping-fan-cover.py
	$(call export_selected_object,$<,build_wrapping_fan_cover)

$(HORN_STLS): horn_parametric_blender.py
	$(call run_single_output_generator,$<,build_horn,EXPORT_STL_PATH)

$(MISSION1_DUMMY_STLS): gopro_mission1_dummy_blender.py
	$(call run_single_output_generator,$<,main,EXPORT_PATH)

$(DUAL_FAN_STLS) &: dual_fan_parametric_blender.py fan_size_presets.py
	$(RM) $(DUAL_FAN_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_STL_PATH']='$(word 1,$(DUAL_FAN_STLS))'; ns['EXPORT_ADAPTER_STL_PATH']='$(word 2,$(DUAL_FAN_STLS))'; ns['build_dual_fan']()"
	$(PDF_PYTHON) -c "from pathlib import Path; paths=[Path(name) for name in '$(DUAL_FAN_STLS)'.split()]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'"

$(FAN_SILENCER_STLS) &: $(FAN_SILENCER_SOURCE_DEPS)
	$(RM) $(FAN_SILENCER_STLS) $(FAN_SILENCER_OBSOLETE_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['FAN_SIZE_MM']=$(FAN_SILENCER_SIZE); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_gopro_fan_silencer']()"
	$(PDF_PYTHON) -c "from pathlib import Path; paths=[Path(name) for name in '$(FAN_SILENCER_STLS)'.split()]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'"

# Grouped targets tell make that one Blender run creates every listed file.
$(FAN_CASE_STLS) &: gopro_fan_case_parametric_blender.py
	$(RM) $(FAN_CASE_ALL_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_gopro_fan_case']()"

# Grouped targets tell make that one Blender run creates every default
# Hockeymom component.  This keeps direct component targets useful and avoids
# rebuilding an unchanged cover every time `make all` is run.  Artifacts behind
# explicit opt-in export switches remain outside this group.
$(HOCKEYMOM_COVER_STLS) &: hockeymom_3_cam_cover_original_style_blender.py gopro_mission1_dummy_blender.py
	$(RM) $(HOCKEYMOM_COVER_STLS) $(HOCKEYMOM_OPTIONAL_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_original_style_cover']()"

hockeymom-cover: $(HOCKEYMOM_COVER_STLS)

clean: clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-silencer clean-fan-case clean-hockeymom-cover \
	clean-dim-pdf clean-fan-case-dim-pdf

clean-flat-fan-cover:
	$(RM) $(FLAT_FAN_COVER_STLS)

clean-wrapping-fan-cover:
	$(RM) $(WRAPPING_FAN_COVER_STLS)

clean-horn:
	$(RM) $(HORN_STLS)

clean-mission1-dummy:
	$(RM) $(MISSION1_DUMMY_STLS)

clean-dual-fan:
	$(RM) $(DUAL_FAN_STLS)

clean-fan-silencer:
	$(RM) $(FAN_SILENCER_KNOWN_STLS) $(FAN_SILENCER_OBSOLETE_STLS)

clean-fan-case:
	$(RM) $(FAN_CASE_ALL_STLS)

clean-hockeymom-cover:
	$(RM) $(HOCKEYMOM_COVER_STLS) $(HOCKEYMOM_OPTIONAL_STLS)

clean-dim-pdf:
	$(RM) $(DIMENSION_PDF)

clean-fan-case-dim-pdf:
	$(RM) $(FAN_CASE_DIMENSION_PDF)
