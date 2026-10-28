include("${CMAKE_CURRENT_LIST_DIR}/MeguvizShaderToolsTargets.cmake")
function(mgst_compile_shaderpack)
  cmake_parse_arguments(MGST "" "REQUEST;OUTPUT" "DEPENDS" ${ARGN})
  if(NOT MGST_REQUEST OR NOT MGST_OUTPUT)
    message(FATAL_ERROR "mgst_compile_shaderpack requires REQUEST and OUTPUT")
  endif()
  get_filename_component(output_parent "${MGST_OUTPUT}" DIRECTORY)
  get_filename_component(output_name "${MGST_OUTPUT}" NAME)
  file(READ "${MGST_REQUEST}" request_json)
  string(JSON profile GET "${request_json}" profile_id)
  string(JSON profile_version GET "${request_json}" profile_version)
  file(WRITE "${MGST_OUTPUT}.index.json" "{\"schema_version\":1,\"profile_id\":\"${profile}\",\"profile_version\":\"${profile_version}\",\"artifacts\":[\"${output_name}.artifact\"]}\n")
  add_custom_command(OUTPUT "${MGST_OUTPUT}.artifact/artifact.json" "${MGST_OUTPUT}.artifact/shader.spv"
    COMMAND MeguvizShaderTools::mgst compile --request "${MGST_REQUEST}" --out-dir "${MGST_OUTPUT}.artifact"
    DEPENDS "${MGST_REQUEST}" ${MGST_DEPENDS} MeguvizShaderTools::mgst
    DEPFILE "${MGST_OUTPUT}.artifact/source.d" VERBATIM)
  add_custom_command(OUTPUT "${MGST_OUTPUT}/manifest.json"
    COMMAND MeguvizShaderTools::mgst pack --index "${MGST_OUTPUT}.index.json" --artifacts "${output_parent}" --out-dir "${MGST_OUTPUT}"
    DEPENDS "${MGST_OUTPUT}.artifact/artifact.json" "${MGST_OUTPUT}.index.json" MeguvizShaderTools::mgst VERBATIM)
endfunction()
