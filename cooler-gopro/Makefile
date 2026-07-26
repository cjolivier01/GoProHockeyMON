BLENDER ?= $(shell command -v blender 2>/dev/null || command -v /home/colivier/Apps/Blender/blender 2>/dev/null || printf '%s' blender)
BLENDER_FLAGS ?= --background --factory-startup
PDF_PYTHON ?= $(shell command -v /home/colivier/miniforge3/bin/python 2>/dev/null || command -v python3 2>/dev/null || printf '%s' python3)

DIMENSION_PDF := hockeymom_3_cam_cover_configuration_dimensions.pdf

FLAT_FAN_COVER_STLS := flat-fan-cover.stl
WRAPPING_FAN_COVER_STLS := wrapping-fan-cover.stl
HORN_STLS := horn_parametric_blender.stl
MISSION1_DUMMY_STLS := gopro_mission1_dummy_recreated.stl
DUAL_FAN_STLS := gopro_dual_fan_parametric.stl
FAN_CASE_STLS := \
	gopro_fan_case_parametric.stl \
	gopro_fan_case_back.stl \
	gopro_fan_case_insert.stl
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
	$(FAN_CASE_STLS)

.DEFAULT_GOAL := print_targets
.DELETE_ON_ERROR:

.PHONY: \
	all print_targets dim-pdf \
	flat-fan-cover wrapping-fan-cover horn mission1-dummy dual-fan fan-case hockeymom-cover \
	clean clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-case clean-hockeymom-cover clean-dim-pdf

# The Hockeymom generator intentionally exports a configuration-dependent
# manifest.  Its phony target therefore performs one authoritative run instead
# of letting absent optional parts or stale files masquerade as current output.
all: $(STL_FILES) hockeymom-cover

print_targets:
	@printf '%s\n' \
		"Available make targets (run 'make <target>'):" \
		'' \
		'STL Builds' \
		'----------' \
		'all                       Build all STL files.' \
		'flat-fan-cover            Build the flat fan cover STL.' \
		'wrapping-fan-cover        Build the wrapping fan cover STL.' \
		'horn                      Build the parametric horn STL.' \
		'mission1-dummy            Build the recreated GoPro Mission 1 dummy STL.' \
		'dual-fan                  Build the parametric dual-fan STL.' \
		'fan-case                  Build the fan case, back, and insert STLs.' \
		'hockeymom-cover           Build all HOCKEYMOM 3 camera-cover component STLs.' \
		'' \
		'Documentation' \
		'-------------' \
		'dim-pdf                   Build the HOCKEYMOM 3 configuration dimension PDF.' \
		'' \
		'Cleanup' \
		'-------' \
		'clean                     Remove all generated STL and dimension-PDF files.' \
		'clean-flat-fan-cover      Remove the flat fan cover STL.' \
		'clean-wrapping-fan-cover  Remove the wrapping fan cover STL.' \
		'clean-horn                Remove the parametric horn STL.' \
		'clean-mission1-dummy      Remove the Mission 1 dummy STL.' \
		'clean-dual-fan            Remove the dual-fan STL.' \
		'clean-fan-case            Remove all fan-case STLs.' \
		'clean-hockeymom-cover     Remove all HOCKEYMOM 3 camera-cover STLs.' \
		'clean-dim-pdf             Remove the HOCKEYMOM 3 configuration dimension PDF.' \
		'' \
		'Meta' \
		'----' \
		'print_targets             Show this help text.'

flat-fan-cover: $(FLAT_FAN_COVER_STLS)
wrapping-fan-cover: $(WRAPPING_FAN_COVER_STLS)
horn: $(HORN_STLS)
mission1-dummy: $(MISSION1_DUMMY_STLS)
dual-fan: $(DUAL_FAN_STLS)
fan-case: $(FAN_CASE_STLS)
dim-pdf: $(DIMENSION_PDF)

$(DIMENSION_PDF): generate_hockeymom_config_dimension_pdf.py \
	hockeymom_3_cam_cover_original_style_blender.py gopro_mission1_dummy_blender.py
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

$(DUAL_FAN_STLS): dual_fan_parametric_blender.py
	$(call run_single_output_generator,$<,build_dual_fan,EXPORT_STL_PATH)

# Grouped targets tell make that one Blender run creates every listed file.
$(FAN_CASE_STLS) &: gopro_fan_case_parametric_blender.py
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_gopro_fan_case']()"

hockeymom-cover: hockeymom_3_cam_cover_original_style_blender.py gopro_mission1_dummy_blender.py
	$(RM) $(HOCKEYMOM_COVER_STLS) $(HOCKEYMOM_OPTIONAL_STLS)
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_original_style_cover']()"

clean: clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-case clean-hockeymom-cover clean-dim-pdf

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

clean-fan-case:
	$(RM) $(FAN_CASE_STLS)

clean-hockeymom-cover:
	$(RM) $(HOCKEYMOM_COVER_STLS) $(HOCKEYMOM_OPTIONAL_STLS)

clean-dim-pdf:
	$(RM) $(DIMENSION_PDF)
