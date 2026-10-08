"""Build a local copy of Arduino's BLE service with safe NimBLE discovery.

The upstream callback publishes completion after waking its caller. On another
core that caller can start discovery again and leak duplicate characteristics.
Descriptor discovery also scans past the owning characteristic and leaks
duplicate descriptor UUIDs. Bound the range and preserve allocation ownership.
Keep this workaround in the build directory; never modify the shared framework.
Unknown upstream code is rejected so a framework upgrade requires review.
"""
from pathlib import Path


def patch_source(source: str) -> str:
    replacements = (
        (
            "  BLEUtils::taskRelease(*pTaskData, error->status);\n"
            "  service->m_haveCharacteristics = true;\n"
            '  log_d("<< Characteristic Discovered");',
            "  // Publish the completed cache before the other core resumes.\n"
            "  service->m_haveCharacteristics = (error->status == BLE_HS_EDONE);\n"
            "  BLEUtils::taskRelease(*pTaskData, error->status);\n"
            '  log_d("<< Characteristic Discovered");',
        ),
        (
            "  if (error->status == 0) {\n"
            "    // Found a service - add it to the vector\n"
            "    BLERemoteCharacteristic *pRemoteCharacteristic = new BLERemoteCharacteristic(service, chr);",
            "  if (error->status == 0) {\n"
            "    // Retrying partial discovery must retain the existing owner.\n"
            "    if (service->m_characteristicMapByHandle.find(chr->val_handle) != service->m_characteristicMapByHandle.end()) {\n"
            "      return 0;\n"
            "    }\n"
            "    // Found a service - add it to the vector\n"
            "    BLERemoteCharacteristic *pRemoteCharacteristic = new BLERemoteCharacteristic(service, chr);",
        ),
    )
    return apply_replacements(source, replacements)


def patch_characteristic_source(source: str) -> str:
    replacements = (
        (
            "  // If this is the last handle then there are no descriptors\n"
            "  if (m_handle == getRemoteService()->getEndHandle()) {",
            "  // NimBLE reports the requested start handle for every result; it\n"
            "  // does not identify which later characteristic owns an attribute.\n"
            "  // Stop before the next characteristic declaration.\n"
            "  BLERemoteService *service = getRemoteService();\n"
            "  uint16_t endHandle = service->getEndHandle();\n"
            "  auto next = service->m_characteristicMapByHandle.upper_bound(m_handle);\n"
            "  if (next != service->m_characteristicMapByHandle.end()) {\n"
            "    endHandle = next->second->m_defHandle - 1;\n"
            "  }\n"
            "  if (m_handle >= endHandle) {",
        ),
        (
            "    getRemoteService()->getClient()->getConnId(), m_handle, getRemoteService()->getEndHandle(), BLERemoteCharacteristic::descriptorDiscCB, &filter",
            "    getRemoteService()->getClient()->getConnId(), m_handle, endHandle, BLERemoteCharacteristic::descriptorDiscCB, &filter",
        ),
        (
            "    characteristic->m_descriptorMap.insert(\n"
            "      std::pair<std::string, BLERemoteDescriptor *>(pNewRemoteDescriptor->getUUID().toString().c_str(), pNewRemoteDescriptor)\n"
            "    );",
            "    auto inserted = characteristic->m_descriptorMap.insert(\n"
            "      std::pair<std::string, BLERemoteDescriptor *>(pNewRemoteDescriptor->getUUID().toString().c_str(), pNewRemoteDescriptor)\n"
            "    );\n"
            "    if (!inserted.second) {\n"
            "      delete pNewRemoteDescriptor;\n"
            "    }",
        ),
    )
    return apply_replacements(source, replacements)


def apply_replacements(source, replacements):
    for old, new in replacements:
        if source.count(old) == 1:
            source = source.replace(old, new, 1)
        elif source.count(new) != 1:
            raise RuntimeError(
                "Arduino BLE discovery source changed; review scripts/patch_ble_discovery.py "
                "before building this framework version"
            )
    return source


def register_middleware(env):
    def patched_source(build_env, node):
        original = Path(node.srcnode().get_abspath())
        patcher = patch_source if original.name == "BLERemoteService.cpp" else patch_characteristic_source
        patched = patcher(original.read_text())
        destination = Path(build_env.subst("$BUILD_DIR")) / "patched_ble" / original.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_text() != patched:
            destination.write_text(patched)
        build_env.AppendUnique(CPPPATH=[str(original.parent)])
        return build_env.File(str(destination))

    env.AddBuildMiddleware(patched_source, "*/BLE/src/BLERemoteService.cpp")
    env.AddBuildMiddleware(patched_source, "*/BLE/src/BLERemoteCharacteristic.cpp")


if "Import" in globals():
    Import("env")
    register_middleware(env)
