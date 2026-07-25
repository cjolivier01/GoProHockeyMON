BLENDER ?= $(shell command -v blender 2>/dev/null || command -v /home/colivier/Apps/Blender/blender 2>/dev/null || printf '%s' blender)
BLENDER_FLAGS ?= --background --factory-startup

FLAT_FAN_COVER_STLS := flat-fan-cover.stl
WRAPPING_FAN_COVER_STLS := wrapping-fan-cover.stl
HORN_STLS := horn_parametric_blender.stl
MISSION1_DUMMY_STLS := gopro_mission1_dummy_recreated.stl
DUAL_FAN_STLS := gopro_dual_fan_parametric.stl
FAN_CASE_STLS := \
	gopro_fan_case_parametric.stl \
	gopro_fan_case_back.stl \
	gopro_fan_case_insert.stl
VEO_COVER_STLS := \
	veo_3_cam_cover_original_style_base.stl \
	veo_3_cam_cover_original_style_lid.stl \
	veo_3_cam_cover_camera_bracket_1.stl \
	veo_3_cam_cover_camera_bracket_2.stl \
	veo_3_cam_cover_rotating_camera_cartridge.stl \
	veo_3_cam_cover_worm_inner_bearing_cap.stl \
	veo_3_cam_cover_worm_outer_bearing_cap.stl \
	veo_3_cam_cover_fan_acoustic_trough.stl \
	veo_3_cam_cover_fan_acoustic_lid.stl \
	veo_3_cam_cover_fan_acoustic_boot_seal_1.stl \
	veo_3_cam_cover_fan_acoustic_boot_seal_2.stl \
	veo_3_cam_cover_original_style.stl

STL_FILES := \
	$(FLAT_FAN_COVER_STLS) \
	$(WRAPPING_FAN_COVER_STLS) \
	$(HORN_STLS) \
	$(MISSION1_DUMMY_STLS) \
	$(DUAL_FAN_STLS) \
	$(FAN_CASE_STLS) \
	$(VEO_COVER_STLS)

.DEFAULT_GOAL := print_targets
.DELETE_ON_ERROR:

.PHONY: \
	all print_targets \
	flat-fan-cover wrapping-fan-cover horn mission1-dummy dual-fan fan-case veo-cover \
	clean clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-case clean-veo-cover

all: $(STL_FILES)

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
		'veo-cover                 Build all VEO 3 camera-cover component STLs.' \
		'' \
		'Cleanup' \
		'-------' \
		'clean                     Remove all generated STL files.' \
		'clean-flat-fan-cover      Remove the flat fan cover STL.' \
		'clean-wrapping-fan-cover  Remove the wrapping fan cover STL.' \
		'clean-horn                Remove the parametric horn STL.' \
		'clean-mission1-dummy      Remove the Mission 1 dummy STL.' \
		'clean-dual-fan            Remove the dual-fan STL.' \
		'clean-fan-case            Remove all fan-case STLs.' \
		'clean-veo-cover           Remove all VEO 3 camera-cover STLs.' \
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
veo-cover: $(VEO_COVER_STLS)

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

$(VEO_COVER_STLS) &: veo_3_cam_cover_original_style_blender.py gopro_mission1_dummy_blender.py
	$(BLENDER) $(BLENDER_FLAGS) --python-expr \
		"p='$<'; ns={'__name__':'make_stl','__file__':p}; exec(compile(open(p,'rb').read(),p,'exec'),ns); ns['EXPORT_STL']=True; ns['EXPORT_DIRECTORY']='$(CURDIR)'; ns['build_original_style_cover']()"

clean: clean-flat-fan-cover clean-wrapping-fan-cover clean-horn \
	clean-mission1-dummy clean-dual-fan clean-fan-case clean-veo-cover

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

clean-veo-cover:
	$(RM) $(VEO_COVER_STLS)
