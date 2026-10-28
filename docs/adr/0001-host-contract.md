# ADR 0001: conservative host contracts

Status: accepted for the local Windows host candidate, 2026-10-28.

The host links pinned glslang, SPIRV-Tools validator and SPIRV-Reflect directly.
No compiler is searched on PATH at runtime. No GPU is enumerated. The source lock
and native compiler executable hash, version, build configuration and mgst source
fingerprint participate in the effective toolchain identity.

No new JSON or crypto production dependency was authorized. The CLI therefore
accepts a deliberately restricted JSON grammar: null, booleans, UTF-8 strings,
arrays, sorted string-keyed objects, and integers in the interoperable range
[-9007199254740991, 9007199254740991]. Floating JSON numbers are rejected; floating
specialization values use explicit IEEE bit strings. Duplicate keys, invalid
UTF-8/surrogates, excessive depth/node count, unsafe integers and trailing input
fail before any compiler or reflector call. This is a product configuration
grammar, not a general JSON/schema library. SHA-256 uses the FIPS 180-4 algorithm
and is compared against independent CPython hashlib boundary and NIST vectors.

Canonical form is UTF-8, lexicographically sorted keys, no insignificant spaces,
no escaped slash, lowercase control escapes, and no trailing newline in the
hashed representation. Files add one newline. `manifest_hash` hashes the canonical
manifest excluding only `manifest_hash`. Reflection, source and SPIR-V SHA-256 identities cover exact file bytes, including
the reflection file's terminal newline. A prior canonical-only reflection hash
was rejected by Compute's independent file-byte check; that failed run is retained.

Requests list a complete include name/content closure. Source and include paths
must remain inside the request directory, including symlink resolution. No parent
traversal or absolute input is accepted. Outputs publish from a unique temporary
directory to a previously nonexistent destination. A failure retains temporary
diagnostics and cannot replace a valid output. CMake callers select a new build
output generation when changing a request; an old immutable destination fails.

ncnn-compat uses pinned resource/helper recipes and explicit effective Options.
Ordered device macro tokens belong to the target-facts capture contract. Synthetic
facts are host fixtures only. Exact byte comparison against a target runtime,
driver execution, numerical equivalence and no-runtime-compiler qualification
remain blocked pending the Compute/RIFE runner and actual hardware. Ordinary
runtime compiler fallback remains required. No strip-debug optimization is used.

Only Windows x86-64 has been built in this environment. Linux and macOS presets
are supplied for native runners; their binaries and cross-host reproducibility
are not claimed. This limitation prevents a complete S4/S5 profile gate.
