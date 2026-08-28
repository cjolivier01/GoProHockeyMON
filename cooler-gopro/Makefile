# GNU Make 4.3 or newer is required for the grouped targets used below.
REQUIRED_GNU_MAKE_MAJOR := 4
REQUIRED_GNU_MAKE_MINOR := 3
DETECTED_GNU_MAKE_VERSION_WORDS := $(subst ., ,$(MAKE_VERSION))
DETECTED_GNU_MAKE_MAJOR := $(word 1,$(DETECTED_GNU_MAKE_VERSION_WORDS))
DETECTED_GNU_MAKE_MINOR := $(word 2,$(DETECTED_GNU_MAKE_VERSION_WORDS))
SUPPORTED_GNU_MAKE_VERSION := $(shell \
	if [ "$(DETECTED_GNU_MAKE_MAJOR)" -gt "$(REQUIRED_GNU_MAKE_MAJOR)" ] || \
		{ [ "$(DETECTED_GNU_MAKE_MAJOR)" -eq "$(REQUIRED_GNU_MAKE_MAJOR)" ] && \
		[ "$(DETECTED_GNU_MAKE_MINOR)" -ge "$(REQUIRED_GNU_MAKE_MINOR)" ]; }; then \
		printf '%s' yes; \
	fi)
ifeq ($(SUPPORTED_GNU_MAKE_VERSION),)
$(error GNU Make 4.3 or newer is required; detected $(MAKE_VERSION). On macOS, install a current GNU Make and run this file with gmake)
endif

BLENDER ?= $(shell command -v blender 2>/dev/null || command -v /home/colivier/Apps/Blender/blender 2>/dev/null || printf '%s' blender)
BLENDER_FLAGS ?= --background --factory-startup
PDF_PYTHON ?= $(shell command -v python 2>/dev/null || command -v python3 2>/dev/null || printf '%s' python3)

DIMENSION_PDF := hockeymom_cam_case_configuration_dimensions.pdf
HOCKEYMOM_CAM_CASE_OBSOLETE_DIMENSION_PDFS := \
	hockeymom_3_cam_cover_configuration_dimensions.pdf
HOCKEYMOM_CAM_CASE_OBSOLETE_IMAGES := \
	hockeymom_3_cam_cover_original_style.png
FAN_CASE_DIMENSION_PDF := gopro_fan_case_configuration_dimensions.pdf
DUAL_FAN_DIMENSION_PDF := gopro_dual_fan_configuration_dimensions.pdf

FLAT_FAN_COVER_STLS := flat-fan-cover.stl
WRAPPING_FAN_COVER_STLS := wrapping-fan-cover.stl
HORN_STLS := horn_parametric_blender.stl
MISSION1_DUMMY_STLS := gopro_mission1_dummy_recreated.stl
MISSION1_FIELD_CASE_STLS := \
	mission1_field_case_base.stl \
	mission1_field_case_lid.stl \
	mission1_field_case_lower_tray_tpu.stl \
	mission1_field_case_lid_retainer_tpu.stl \
	mission1_field_case_gasket_tpu.stl \
	mission1_field_case_over_center_latch_handle_print_two.stl \
	mission1_field_case_over_center_latch_bail_print_two.stl \
	mission1_field_case_latch_base_pin_print_two.stl \
	mission1_field_case_latch_link_pin_print_two.stl \
	mission1_field_case_hinge_pin.stl \
	mission1_field_case_lid_title_inlay.stl \
	mission1_field_case_lid_subtitle_inlay.stl
MISSION1_FIELD_CASE_3MF := mission1_field_case_ams_project.3mf
MISSION1_FIELD_CASE_OUTPUTS := $(MISSION1_FIELD_CASE_STLS) $(MISSION1_FIELD_CASE_3MF)
MISSION1_FIELD_CASE_OBSOLETE_STLS := \
	mission1_field_case_lower_insert.stl \
	mission1_field_case_latch_print_two.stl \
	mission1_field_case_pelican_latch_print_two.stl \
	mission1_field_case_latch_pin_print_two.stl
DUAL_FAN_HOLDER_STL := gopro_dual_fan_parametric.stl
DUAL_FAN_ADAPTER_STLS := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('dual_fan_parametric_blender.py', encoding='utf-8').read()); names={'GOPRO_ADAPTER_PRONG_COUNTS','GOPRO_ADAPTER_PRONG_COUNT','EXPORT_ADAPTER_STL_PATHS','EXPORT_ADAPTER_STL_PATH'}; values={target.id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,(ast.Assign,ast.AnnAssign)) for target in ([node.target] if isinstance(node,ast.AnnAssign) else node.targets) if isinstance(target,ast.Name) and target.id in names}; legacy_count=values['GOPRO_ADAPTER_PRONG_COUNT']; counts=(legacy_count,) if legacy_count is not None else values['GOPRO_ADAPTER_PRONG_COUNTS']; paths=dict(values['EXPORT_ADAPTER_STL_PATHS']); legacy_path=values['EXPORT_ADAPTER_STL_PATH']; paths[counts[0]]=(legacy_path or 'gopro_dual_fan_adapter.stl') if legacy_count is not None else (legacy_path or paths[counts[0]]); print(' '.join(paths[count] for count in counts))")
DUAL_FAN_KNOWN_ADAPTER_STLS := \
	gopro_dual_fan_adapter.stl \
	gopro_dual_fan_adapter_2_prong.stl \
	gopro_dual_fan_adapter_3_prong.stl
DUAL_FAN_STLS := $(DUAL_FAN_HOLDER_STL) $(DUAL_FAN_ADAPTER_STLS)
DUAL_FAN_ALL_STLS := $(sort $(DUAL_FAN_STLS) $(DUAL_FAN_KNOWN_ADAPTER_STLS))
DUAL_FAN_OPTIONAL_STLS := $(foreach size,40 60 80 120,\
	gopro_single_fan_$(size)mm_airflow_splitter.stl)
DUAL_FAN_BUILD_SENTINEL := .gopro_dual_fan_build_complete
FAN_SILENCER_SIZE ?= 40
FAN_SILENCER_SUPPORTED_SIZES := 40 60 80 120
ifeq ($(filter $(FAN_SILENCER_SIZE),$(FAN_SILENCER_SUPPORTED_SIZES)),)
$(error FAN_SILENCER_SIZE must be one of: $(FAN_SILENCER_SUPPORTED_SIZES))
endif
FAN_SILENCER_PREFIX := gopro_$(FAN_SILENCER_SIZE)mm_fan_silencer
FAN_SILENCER_STLS := $(FAN_SILENCER_PREFIX).stl
FAN_SILENCER_CROSS_SECTION := $(FAN_SILENCER_PREFIX)_cross_section.png
FAN_SILENCER_MOUNTED_VIEW := $(FAN_SILENCER_PREFIX)_mounted_view.png
FAN_SILENCER_SOURCE_DEPS := \
	gopro_fan_silencer_parametric_blender.py \
	fan_size_presets.py \
	thingiverse_5177333_fan_intake_mk4_reference.py
ifeq ($(FAN_SILENCER_SIZE),40)
FAN_SILENCER_SOURCE_DEPS += gopro_fan_case_parametric_blender.py
endif
FAN_SILENCER_KNOWN_STLS := $(foreach size,$(FAN_SILENCER_SUPPORTED_SIZES),\
	gopro_$(size)mm_fan_silencer.stl)
FAN_SILENCER_KNOWN_CROSS_SECTIONS := $(foreach size,$(FAN_SILENCER_SUPPORTED_SIZES),\
	gopro_$(size)mm_fan_silencer_cross_section.png)
FAN_SILENCER_KNOWN_MOUNTED_VIEWS := $(foreach size,$(FAN_SILENCER_SUPPORTED_SIZES),\
	gopro_$(size)mm_fan_silencer_mounted_view.png)
FAN_SILENCER_OBSOLETE_SUFFIXES := \
	_flange.stl \
	_spacer.stl \
	_curved_baffle.stl \
	_center_baffle.stl \
	_alignment_sleeve.stl
FAN_SILENCER_OBSOLETE_STLS := \
	gopro_40mm_fan_silencer_core_half.stl \
	$(foreach size,$(FAN_SILENCER_SUPPORTED_SIZES),\
		$(foreach suffix,$(FAN_SILENCER_OBSOLETE_SUFFIXES),\
			gopro_$(size)mm_fan_silencer$(suffix)))
BAFFLE_CARTRIDGE_ENABLED := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('gopro_fan_case_parametric_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'BAFFLE_CARTRIDGE_ENABLED' for target in node.targets)))")
BAFFLE_CARTRIDGE_MATERIAL_MODE := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('gopro_fan_case_parametric_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'BAFFLE_CARTRIDGE_MATERIAL_MODE' for target in node.targets)))")
FAN_CASE_REAR_FAN_ADAPTER_ENABLED := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('gopro_fan_case_parametric_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'REAR_FAN_ADAPTER_ENABLED' for target in node.targets)))")
HOCKEYMOM_FAN_MOUNT_MODE := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('hockeymom_cam_case_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FAN_MOUNT_MODE' for target in node.targets)))")
HOCKEYMOM_LID_FAN_COVER_ENABLED := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('hockeymom_cam_case_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'LID_FAN_COVER_ENABLED' for target in node.targets)))")
HOCKEYMOM_FAN_ACOUSTIC_ATTENUATOR_ENABLED := $(shell $(PDF_PYTHON) -c "import ast; tree=ast.parse(open('hockeymom_cam_case_blender.py', encoding='utf-8').read()); print(next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FAN_ACOUSTIC_ATTENUATOR_ENABLED' for target in node.targets)))")
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
FAN_CASE_REAR_FAN_ADAPTER_STLS := gopro_fan_case_rear_fan_adapter.stl
ifeq ($(BAFFLE_CARTRIDGE_ENABLED),True)
FAN_CASE_ACTIVE_BAFFLE_STLS := $(FAN_CASE_BAFFLE_BODY_STLS)
ifeq ($(BAFFLE_CARTRIDGE_MATERIAL_MODE),RIGID)
FAN_CASE_ACTIVE_BAFFLE_STLS += $(FAN_CASE_BAFFLE_GASKET_STLS)
endif
endif
ifeq ($(FAN_CASE_REAR_FAN_ADAPTER_ENABLED),True)
FAN_CASE_ACTIVE_REAR_FAN_ADAPTER_STLS := $(FAN_CASE_REAR_FAN_ADAPTER_STLS)
endif
FAN_CASE_STLS := $(FAN_CASE_CORE_STLS) $(FAN_CASE_ACTIVE_BAFFLE_STLS) \
	$(FAN_CASE_ACTIVE_REAR_FAN_ADAPTER_STLS)
FAN_CASE_ALL_STLS := $(FAN_CASE_CORE_STLS) $(FAN_CASE_BAFFLE_STLS) \
	$(FAN_CASE_REAR_FAN_ADAPTER_STLS)
HOCKEYMOM_CAM_CASE_CORE_STLS := \
	hockeymom_cam_case_base.stl \
	hockeymom_cam_case_lid.stl \
	hockeymom_cam_case_camera_bracket_1.stl \
	hockeymom_cam_case_camera_bracket_2.stl \
	hockeymom_cam_case_rotating_camera_cartridge.stl \
	hockeymom_cam_case_idler_shaft_cap.stl \
	hockeymom_cam_case_worm_inner_bearing_cap.stl \
	hockeymom_cam_case_worm_outer_bearing_cap.stl \
	hockeymom_cam_case_worm_knurled_thumb_knob.stl

HOCKEYMOM_CAM_CASE_ACOUSTIC_STLS := \
	hockeymom_cam_case_fan_acoustic_trough.stl \
	hockeymom_cam_case_fan_acoustic_lid.stl \
	hockeymom_cam_case_fan_acoustic_boot_seal_1.stl \
	hockeymom_cam_case_fan_acoustic_boot_seal_2.stl
HOCKEYMOM_CAM_CASE_LID_FAN_STLS := \
	hockeymom_cam_case_lid_fan_fairing.stl \
	hockeymom_cam_case_lid_fan_grille.stl
HOCKEYMOM_CAM_CASE_KEYSTONE_TEST_COUPON_STL := \
	hockeymom_cam_case_keystone_test_coupon.stl
HOCKEYMOM_CAM_CASE_ACTIVE_FAN_STLS :=
ifneq (,$(filter lid_single lid_pair,$(HOCKEYMOM_FAN_MOUNT_MODE)))
ifeq ($(HOCKEYMOM_LID_FAN_COVER_ENABLED),True)
HOCKEYMOM_CAM_CASE_ACTIVE_FAN_STLS += $(HOCKEYMOM_CAM_CASE_LID_FAN_STLS)
endif
endif
ifeq ($(HOCKEYMOM_FAN_MOUNT_MODE),rear_wall_pair)
ifeq ($(HOCKEYMOM_FAN_ACOUSTIC_ATTENUATOR_ENABLED),True)
HOCKEYMOM_CAM_CASE_ACTIVE_FAN_STLS += $(HOCKEYMOM_CAM_CASE_ACOUSTIC_STLS)
endif
endif
HOCKEYMOM_CAM_CASE_STLS := $(HOCKEYMOM_CAM_CASE_CORE_STLS) \
	$(HOCKEYMOM_CAM_CASE_ACTIVE_FAN_STLS)

# These are emitted only when their corresponding reference/service export
# switches are enabled.  Keep them out of the grouped build prerequisites,
# but include them in cleanup so stale optional artifacts cannot survive a
# configuration change.
HOCKEYMOM_CAM_CASE_OPTIONAL_STLS := \
	hockeymom_cam_case_ASSEMBLY_REFERENCE_NOT_FOR_PRINT.stl \
	hockeymom_cam_case_lid_fan_cover.stl \
	hockeymom_cam_case_cartridge_removable_front_stop.stl \
	hockeymom_cam_case_purchased_worm_reference.stl \
	hockeymom_cam_case_purchased_worm_wheel_reference.stl \
	hockeymom_cam_case_purchased_4mm_idler_shaft_reference.stl \
	hockeymom_cam_case_idler_spur_pinion.stl \
	hockeymom_cam_case_fan_gasket_1.stl \
	hockeymom_cam_case_fan_gasket_2.stl \
	$(HOCKEYMOM_CAM_CASE_KEYSTONE_TEST_COUPON_STL)
HOCKEYMOM_CAM_CASE_ALL_STLS := $(sort \
	$(HOCKEYMOM_CAM_CASE_CORE_STLS) \
	$(HOCKEYMOM_CAM_CASE_ACOUSTIC_STLS) \
	$(HOCKEYMOM_CAM_CASE_LID_FAN_STLS) \
	$(HOCKEYMOM_CAM_CASE_OPTIONAL_STLS))

# Purge generated artifacts from before the hockeymom_cam_case rename so an
# update cannot leave obsolete and current parts side by side.
HOCKEYMOM_CAM_CASE_OBSOLETE_STLS := \
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
	hockeymom_3_cam_cover_fan_acoustic_boot_seal_2.stl \
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
	$(MISSION1_FIELD_CASE_STLS) \
	$(DUAL_FAN_STLS) \
	$(FAN_SILENCER_STLS) \
	$(FAN_CASE_STLS)

.DEFAULT_GOAL := print_targets
.DELETE_ON_ERROR:

.PHONY: \
	all print_targets dim-pdf check-dim-pdf-sync \
	dual-fan-dim-pdf check-dual-fan-dim-pdf-sync \
	fan-case-dim-pdf check-fan-case-dim-pdf-sync \
	flat-fan-cover wrapping-fan-cover horn mission1-dummy mission1-field-case dual-fan fan-silencer \
	fan-silencer-cross-section fan-silencer-mounted-view fan-case hockeymom-cam-case \
	hockeymom-keystone-test-coupon \
	clean clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-mission1-field-case clean-dual-fan clean-fan-silencer clean-fan-case clean-hockeymom-cam-case \
	clean-dim-pdf clean-dual-fan-dim-pdf clean-fan-case-dim-pdf

# Keep every generated dimension guide synchronized with its model sources.
# Each PDF target also depends on its generator, so any configuration or
# documentation-layout change is reflected by the next normal `make all`.
all: $(STL_FILES) $(MISSION1_FIELD_CASE_3MF) $(HOCKEYMOM_CAM_CASE_STLS) \
	$(DUAL_FAN_DIMENSION_PDF) $(FAN_CASE_DIMENSION_PDF) $(DIMENSION_PDF) \
	check-dual-fan-dim-pdf-sync check-fan-case-dim-pdf-sync check-dim-pdf-sync

print_targets:
	@printf '%s\n' \
		"Available make targets (run 'make <target>'):" \
		'' \
		'Print Builds' \
		'------------' \
		'all                       Build all print files and synchronized dimension PDFs.' \
		'flat-fan-cover            Build the flat fan cover STL.' \
		'wrapping-fan-cover        Build the wrapping fan cover STL.' \
		'horn                      Build the parametric horn STL.' \
		'mission1-dummy            Build the recreated GoPro Mission 1 dummy STL.' \
		'mission1-field-case       Build twelve part STLs plus the complete AMS-ready 3MF project.' \
		'dual-fan                  Build the fan holder and both GoPro adapter variants; optional splitter follows CONFIG.' \
		'fan-silencer              Build a fan silencer; set FAN_SILENCER_SIZE=40/60/80/120.' \
		'fan-case                  Build the case, optional rear-fan horn, baffle, buttons, gate, and keeper STLs.' \
		'hockeymom-cam-case        Build all Hockeymom camera-case component STLs.' \
		'hockeymom-keystone-test-coupon  Build a small standalone keystone socket fit-test STL.' \
		'' \
		'Renders' \
		'-------' \
		'fan-silencer-cross-section  Render its assembled case/silencer/fan center section.' \
		'fan-silencer-mounted-view  Render the silencer mounted on its fan intake.' \
		'' \
		'Documentation' \
		'-------------' \
		'dual-fan-dim-pdf          Build the dual-fan holder configuration dimension PDF.' \
		'check-dual-fan-dim-pdf-sync  Verify dual-fan PDF synchronization and drawing coverage.' \
		'fan-case-dim-pdf          Build the fan-case configuration dimension PDF.' \
		'check-fan-case-dim-pdf-sync  Verify PDF synchronization and engineering-drawing coverage.' \
		'dim-pdf                   Build the Hockeymom camera-case configuration dimension PDF.' \
		'check-dim-pdf-sync        Verify the PDF matches its model and generator sources.' \
		'' \
		'Cleanup' \
		'-------' \
		'clean                     Remove all generated print and dimension-PDF files.' \
		'clean-flat-fan-cover      Remove the flat fan cover STL.' \
		'clean-wrapping-fan-cover  Remove the wrapping fan cover STL.' \
		'clean-horn                Remove the parametric horn STL.' \
		'clean-mission1-dummy      Remove the Mission 1 dummy STL.' \
		'clean-mission1-field-case Remove all dual Mission 1 field-case print outputs.' \
		'clean-dual-fan            Remove the dual-fan holder and adapter STLs.' \
		'clean-fan-silencer        Remove fan-silencer STLs and generated render images.' \
		'clean-fan-case            Remove all fan-case STLs.' \
		'clean-hockeymom-cam-case  Remove all Hockeymom camera-case STLs.' \
		'clean-dual-fan-dim-pdf    Remove the dual-fan configuration dimension PDF.' \
		'clean-fan-case-dim-pdf    Remove the fan-case configuration dimension PDF.' \
		'clean-dim-pdf             Remove the Hockeymom camera-case configuration dimension PDF.' \
		'' \
		'Meta' \
		'----' \
		'print_targets             Show this help text.'

flat-fan-cover: $(FLAT_FAN_COVER_STLS)
wrapping-fan-cover: $(WRAPPING_FAN_COVER_STLS)
horn: $(HORN_STLS)
mission1-dummy: $(MISSION1_DUMMY_STLS)
mission1-field-case: $(MISSION1_FIELD_CASE_OUTPUTS)
dual-fan: $(DUAL_FAN_STLS)
fan-silencer: $(FAN_SILENCER_STLS)
fan-silencer-cross-section: $(FAN_SILENCER_CROSS_SECTION)
fan-silencer-mounted-view: $(FAN_SILENCER_MOUNTED_VIEW)
fan-case: $(FAN_CASE_STLS)
dual-fan-dim-pdf: $(DUAL_FAN_DIMENSION_PDF)
fan-case-dim-pdf: $(FAN_CASE_DIMENSION_PDF)
dim-pdf: $(DIMENSION_PDF)

check-dual-fan-dim-pdf-sync: $(DUAL_FAN_DIMENSION_PDF)
	$(PDF_PYTHON) generate_dual_fan_config_dimension_pdf.py --check-sync

check-dim-pdf-sync: $(DIMENSION_PDF)
	$(PDF_PYTHON) generate_hockeymom_cam_case_dimension_pdf.py --check-sync

check-fan-case-dim-pdf-sync: $(FAN_CASE_DIMENSION_PDF)
	$(PDF_PYTHON) generate_fan_case_config_dimension_pdf.py --check-sync

$(DIMENSION_PDF): generate_hockeymom_cam_case_dimension_pdf.py \
	hockeymom_cam_case_blender.py gopro_mission1_dummy_blender.py \
	fan_size_presets.py
	$(PDF_PYTHON) $<

$(FAN_CASE_DIMENSION_PDF): generate_fan_case_config_dimension_pdf.py \
	gopro_fan_case_parametric_blender.py fan_size_presets.py $(FAN_CASE_STLS)
	$(PDF_PYTHON) $<

$(DUAL_FAN_DIMENSION_PDF): generate_dual_fan_config_dimension_pdf.py \
	dual_fan_parametric_blender.py fan_size_presets.py $(DUAL_FAN_STLS)
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

# One generator emits every printable field-case component, including both
# separate color inlays, plus the AMS project. Reference mockups stay disabled
# for print-output builds. The grouped rule records that one invocation updates
# the complete kit while retaining normal timestamp-based incremental builds.
$(MISSION1_FIELD_CASE_OUTPUTS) &: mission1_field_case_blender.py \
	gopro_mission1_dummy_blender.py
	$(RM) $(MISSION1_FIELD_CASE_OUTPUTS) $(MISSION1_FIELD_CASE_OBSOLETE_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-exit-code 1 --python-expr \
		"import os; p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']=os.getcwd(); ns['BUILD_REFERENCE_MOCKUPS']=False; ns['build_mission1_field_case']()"
	$(PDF_PYTHON) -c "from pathlib import Path; import zipfile; paths=[Path(name) for name in '$(MISSION1_FIELD_CASE_OUTPUTS)'.split()]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'; stl_payloads=[(path, path.read_bytes()) for path in paths[:-1]]; invalid_stls=[str(path) for path, data in stl_payloads if len(data) < 84 or len(data) != 84 + 50 * int.from_bytes(data[80:84], 'little')]; assert not invalid_stls, f'Invalid binary STL outputs: {invalid_stls}'; archive=zipfile.ZipFile(paths[-1]); bad_member=archive.testzip(); archive.close(); assert bad_member is None, f'Corrupt 3MF member: {bad_member}'"

$(DUAL_FAN_STLS) &: dual_fan_parametric_blender.py fan_size_presets.py
	$(RM) $(DUAL_FAN_ALL_STLS) $(DUAL_FAN_OPTIONAL_STLS) $(DUAL_FAN_BUILD_SENTINEL)
	$(BLENDER) $(BLENDER_FLAGS) --python-exit-code 1 --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_STL_PATH']='$(DUAL_FAN_HOLDER_STL)'; ns['build_dual_fan'](); __import__('pathlib').Path('$(DUAL_FAN_BUILD_SENTINEL)').write_text('complete',encoding='utf-8')"
	$(PDF_PYTHON) -c "from pathlib import Path; sentinel=Path('$(DUAL_FAN_BUILD_SENTINEL)'); paths=[Path(name) for name in '$(DUAL_FAN_STLS)'.split()]+[sentinel]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'; sentinel.unlink()"

$(FAN_SILENCER_STLS): $(FAN_SILENCER_SOURCE_DEPS)
	$(RM) $(FAN_SILENCER_STLS) $(FAN_SILENCER_OBSOLETE_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['FAN_SIZE_MM']=$(FAN_SILENCER_SIZE); ns['EXPORT_STL']=True; ns['EXPORT_STL_PATH']='$@'; ns['build_gopro_fan_silencer']()"
	$(PDF_PYTHON) -c "from pathlib import Path; paths=[Path(name) for name in '$(FAN_SILENCER_STLS)'.split()]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'"

$(FAN_SILENCER_CROSS_SECTION): $(FAN_SILENCER_SOURCE_DEPS)
	$(RM) $@
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_cross_section','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['FAN_SIZE_MM']=$(FAN_SILENCER_SIZE); ns['RENDER_CROSS_SECTION']=True; ns['CROSS_SECTION_PATH']='$@'; ns['build_gopro_fan_silencer']()"
	$(PDF_PYTHON) -c "from pathlib import Path; path=Path('$@'); assert path.is_file() and path.stat().st_size > 0, f'Missing Blender output: {path}'"

$(FAN_SILENCER_MOUNTED_VIEW): $(FAN_SILENCER_SOURCE_DEPS)
	$(RM) $@
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_mounted_view','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['FAN_SIZE_MM']=$(FAN_SILENCER_SIZE); ns['RENDER_MOUNTED_VIEW']=True; ns['MOUNTED_VIEW_PATH']='$@'; ns['build_gopro_fan_silencer']()"
	$(PDF_PYTHON) -c "from pathlib import Path; path=Path('$@'); assert path.is_file() and path.stat().st_size > 0, f'Missing Blender output: {path}'"

# Grouped targets tell make that one Blender run creates every listed file.
$(FAN_CASE_STLS) &: gopro_fan_case_parametric_blender.py fan_size_presets.py
	$(RM) $(FAN_CASE_ALL_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"import os,sys; p='$<'; sys.path.insert(0,os.path.dirname(os.path.abspath(p))); ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_gopro_fan_case']()"

# Grouped targets tell make that one Blender run creates every default
# Hockeymom component.  This keeps direct component targets useful and avoids
# rebuilding an unchanged cover every time `make all` is run.  Artifacts behind
# explicit opt-in export switches remain outside this group.
$(HOCKEYMOM_CAM_CASE_STLS) &: hockeymom_cam_case_blender.py \
	gopro_mission1_dummy_blender.py fan_size_presets.py
	$(RM) $(HOCKEYMOM_CAM_CASE_ALL_STLS) \
		$(HOCKEYMOM_CAM_CASE_OBSOLETE_STLS) \
		$(HOCKEYMOM_CAM_CASE_OBSOLETE_IMAGES)
	$(BLENDER) $(BLENDER_FLAGS) --python-exit-code 1 --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_hockeymom_cam_case']()"
	$(PDF_PYTHON) -c "from pathlib import Path; paths=[Path(name) for name in '$(HOCKEYMOM_CAM_CASE_STLS)'.split()]; missing=[str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]; assert not missing, f'Missing Blender outputs: {missing}'"

hockeymom-cam-case: $(HOCKEYMOM_CAM_CASE_STLS)

$(HOCKEYMOM_CAM_CASE_KEYSTONE_TEST_COUPON_STL): hockeymom_cam_case_blender.py \
	gopro_mission1_dummy_blender.py fan_size_presets.py
	$(RM) $@
	$(BLENDER) $(BLENDER_FLAGS) --python-exit-code 1 --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['KEYSTONE_TEST_COUPON_STL_NAME']='$@'; ns['build_bottom_keystone_test_coupon']()"
	$(PDF_PYTHON) -c "from pathlib import Path; path=Path('$@'); assert path.is_file() and path.stat().st_size > 0, f'Missing Blender output: {path}'"

hockeymom-keystone-test-coupon: $(HOCKEYMOM_CAM_CASE_KEYSTONE_TEST_COUPON_STL)

clean: clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-mission1-field-case clean-dual-fan clean-fan-silencer clean-fan-case clean-hockeymom-cam-case \
	clean-dual-fan-dim-pdf clean-fan-case-dim-pdf clean-dim-pdf

clean-flat-fan-cover:
	$(RM) $(FLAT_FAN_COVER_STLS)

clean-wrapping-fan-cover:
	$(RM) $(WRAPPING_FAN_COVER_STLS)

clean-horn:
	$(RM) $(HORN_STLS)

clean-mission1-dummy:
	$(RM) $(MISSION1_DUMMY_STLS)

clean-mission1-field-case:
	$(RM) $(MISSION1_FIELD_CASE_OUTPUTS) $(MISSION1_FIELD_CASE_OBSOLETE_STLS)

clean-dual-fan:
	$(RM) $(DUAL_FAN_ALL_STLS) $(DUAL_FAN_OPTIONAL_STLS) $(DUAL_FAN_BUILD_SENTINEL)

clean-fan-silencer:
	$(RM) $(FAN_SILENCER_KNOWN_STLS) $(FAN_SILENCER_KNOWN_CROSS_SECTIONS) \
		$(FAN_SILENCER_KNOWN_MOUNTED_VIEWS) $(FAN_SILENCER_OBSOLETE_STLS)

clean-fan-case:
	$(RM) $(FAN_CASE_ALL_STLS)

clean-hockeymom-cam-case:
	$(RM) $(HOCKEYMOM_CAM_CASE_ALL_STLS) \
		$(HOCKEYMOM_CAM_CASE_OBSOLETE_STLS) \
		$(HOCKEYMOM_CAM_CASE_OBSOLETE_IMAGES)

clean-dual-fan-dim-pdf:
	$(RM) $(DUAL_FAN_DIMENSION_PDF)

clean-dim-pdf:
	$(RM) $(DIMENSION_PDF) $(HOCKEYMOM_CAM_CASE_OBSOLETE_DIMENSION_PDFS)

clean-fan-case-dim-pdf:
	$(RM) $(FAN_CASE_DIMENSION_PDF)
