# Önek kuralı denetimi

`python3 onek_denetim.py` çıktısı. Girdi: `veri/bin/olcek/dogrulama.jsonl`, `veri/bin/olcek/egitim.jsonl`, `veri/bin/olcek/test.jsonl`.

341 proje, 82804 benzersiz ad. `hazirla_olcek.py` varsayılan kuralı (siklik) 70 projede proje adıyla ilgisiz bir öneki atıyor; bu 10247 adın (%12.4) eğitim/test hedefini değiştiriyor.

Düzeltme: `lora/hazirla_olcek.py --onek-kurali proje` (aynı eşik, önek proje adıyla ilişkili olmalı).

## Projeler

| proje | ad | siklik öneki | proje kuralı öneki | yanlış kırpılan | çakışan hedef |
|---|---:|---|---|---:|---:|
| catime | 1640 | ma | - | 1606 | 0 |
| ttgo_twatch_library | 1738 | lv | - | 1115 | 14 |
| cglm | 728 | glmc | - | 712 | 0 |
| wasm3 | 1273 | op | - | 685 | 3 |
| php-ext-xlswriter | 1525 | lxlsx | - | 589 | 0 |
| cmsis-dsp | 563 | arm | - | 557 | 0 |
| kha | 694 | hl | - | 426 | 1 |
| sqlcipher | 619 | jim | - | 407 | 7 |
| ziparchive | 387 | mz | - | 328 | 0 |
| lcui | 955 | ui | - | 322 | 0 |
| jerryscript | 449 | ecma | - | 299 | 0 |
| lovr | 480 | ma | - | 251 | 1 |
| libsodium | 597 | crypto | - | 236 | 0 |
| lunasvg | 399 | plutovg | - | 226 | 0 |
| eth.zig | 494 | secp256k1 | - | 199 | 0 |
| bare-metal-programming-guide | 279 | mg | - | 188 | 2 |
| catimg | 219 | stbi | - | 186 | 0 |
| libpostal | 498 | cmp | - | 155 | 0 |
| warp | 382 | waste | - | 147 | 0 |
| quickjs | 287 | js | - | 145 | 0 |
| mcuboot | 171 | zcbor | - | 137 | 0 |
| onedraw | 157 | stbtt | - | 122 | 0 |
| barco | 164 | arg | - | 114 | 0 |
| jansson | 224 | json | - | 104 | 2 |
| fcvvdp | 85 | cvvdp | - | 79 | 0 |
| hash_extender | 110 | buffer | - | 60 | 0 |
| wasm-micro-runtime | 64 | ocall | - | 58 | 0 |
| chia-plotter | 139 | huf | - | 55 | 0 |
| arduino-mqtt | 49 | lwmqtt | - | 49 | 0 |
| gmssl | 46 | skf | - | 46 | 0 |
| shecc | 145 | a64 | - | 45 | 0 |
| wax | 46 | yajl | - | 43 | 0 |
| hactool | 111 | lz4 | - | 38 | 0 |
| easylogger | 42 | elog | - | 36 | 1 |
| arduino-homekit-esp8266 | 57 | homekit | - | 32 | 0 |
| blurhash | 62 | stbiw | - | 27 | 0 |
| wrk2 | 74 | hdr | - | 27 | 1 |
| sajs | 60 | eat | - | 26 | 0 |
| musializer | 28 | nob | - | 25 | 0 |
| tinyusb | 63 | segger | - | 23 | 0 |
| how-to-make-a-computer-operating-system | 29 | trio | - | 19 | 0 |
| nature | 34 | ld | - | 19 | 0 |
| haywire | 47 | http | - | 16 | 0 |
| sslsplit | 42 | logger | - | 15 | 0 |
| wlipsync | 35 | pt | - | 15 | 0 |
| ixy | 30 | virtio | - | 14 | 0 |
| p2pvc | 38 | pautil | - | 14 | 0 |
| stratux | 42 | uat | - | 14 | 0 |
| craft | 29 | ring | - | 13 | 0 |
| fzy | 16 | choices | - | 12 | 0 |
| ios-webkit-debug-proxy | 35 | ht | - | 12 | 0 |
| microcheck | 26 | http | - | 12 | 0 |
| tilck | 25 | term | - | 12 | 0 |
| zclaw | 32 | telegram | - | 12 | 0 |
| photoc | 23 | review | - | 11 | 0 |
| amx | 23 | emulate | - | 10 | 0 |
| esp-homekit | 24 | mdns | - | 10 | 0 |
| traildb | 21 | pqueue | - | 10 | 0 |
| ctypes.sh | 24 | rb | - | 9 | 0 |
| dperf | 10 | config | - | 9 | 0 |
| easyhook | 9 | ud | - | 7 | 0 |
| i3 | 7 | sd | - | 7 | 0 |
| libratbag | 13 | rbnode | - | 7 | 0 |
| picomatch | 21 | emit | - | 7 | 0 |
| raddebugger | 18 | sysv | - | 7 | 0 |
| zipline | 9 | js | - | 7 | 0 |
| box64 | 6 | log | - | 6 | 0 |
| cuik | 9 | tls | - | 6 | 0 |
| esp32 | 8 | db | - | 5 | 0 |
| google-authenticator-libpam | 12 | sha1 | - | 5 | 0 |
| adam | 201 | adam | adam | 0 | 0 |
| bcc | 13 | bcc | bcc | 0 | 0 |
| carquet | 44 | carquet | carquet | 0 | 0 |
| cex | 366 | cex | cex | 0 | 0 |
| cjson | 88 | cjson | cjson | 0 | 0 |
| clipmenu | 30 | cs | cs | 0 | 0 |
| colibri | 136 | coli | coli | 0 | 0 |
| cyaml | 262 | cyaml | cyaml | 0 | 0 |
| envchain | 23 | envchain | envchain | 0 | 0 |
| facil.io | 768 | fio | fio | 0 | 2 |
| finitestateentropy | 44 | fse | fse | 0 | 0 |
| fmag | 136 | fmag | fmag | 0 | 0 |
| gdrcopy | 12 | gdr | gdr | 0 | 0 |
| guacamole-server | 149 | guac | guac | 0 | 0 |
| h2o | 227 | h2o | h2o | 0 | 0 |
| h3.c | 346 | h3 | h3 | 0 | 0 |
| hev-socks5-tunnel | 13 | hev | hev | 0 | 0 |
| iris.c | 303 | iris | iris | 0 | 2 |
| janet | 1348 | janet | janet | 0 | 5 |
| kimi-k3-in-c | 79 | k3 | k3 | 0 | 0 |
| kore | 444 | kore | kore | 0 | 0 |
| libass | 117 | ass | ass | 0 | 0 |
| libcsp | 75 | csp | csp | 0 | 0 |
| libdill | 502 | dns | dns | 0 | 0 |
| libmill | 121 | mill | mill | 0 | 0 |
| libpng | 531 | png | png | 0 | 1 |
| libsoundio | 69 | soundio | soundio | 0 | 0 |
| libucl | 316 | ucl | ucl | 0 | 0 |
| libuv | 113 | uv | uv | 0 | 0 |
| libyaml | 169 | yaml | yaml | 0 | 0 |
| lily | 1114 | lily | lily | 0 | 2 |
| liquid-dsp | 93 | liquid | liquid | 0 | 0 |
| littlefs | 201 | lfs | lfs | 0 | 0 |
| lsquic | 711 | lsquic | lsquic | 0 | 6 |
| lz4 | 170 | lz4 | lz4 | 0 | 0 |
| lzfse | 47 | lzfse | lzfse | 0 | 0 |
| markdown-wasm | 131 | md | md | 0 | 0 |
| mbedtls | 2056 | mbedtls | mbedtls | 0 | 52 |
| md4c | 128 | md | md | 0 | 0 |
| melon | 1552 | mln | mln | 0 | 1 |
| mimalloc | 736 | mi | mi | 0 | 0 |
| minifb | 70 | mfb | mfb | 0 | 0 |
| mu_json_x | 75 | mu | mu | 0 | 0 |
| nanocolor | 36 | nc | nc | 0 | 0 |
| netcode | 162 | netcode | netcode | 0 | 0 |
| nnpack | 35 | nnp | nnp | 0 | 0 |
| painterengine | 4446 | px | px | 0 | 2 |
| phptrace | 17 | pt | pt | 0 | 0 |
| preeny | 52 | preeny | preeny | 0 | 0 |
| qaws | 326 | qaws | qaws | 0 | 0 |
| qoi | 7 | qoi | qoi | 0 | 0 |
| s2n-tls | 126 | s2n | s2n | 0 | 0 |
| sc | 264 | sc | sc | 0 | 0 |
| sfud | 29 | sfud | sfud | 0 | 0 |
| sigar | 66 | sigar | sigar | 0 | 1 |
| silk-v3-decoder | 151 | skp | skp | 0 | 0 |
| skynet | 217 | skynet | skynet | 0 | 0 |
| sparkey | 54 | sparkey | sparkey | 0 | 0 |
| spiffs | 101 | spiffs | spiffs | 0 | 1 |
| tic-80 | 132 | tic | tic | 0 | 0 |
| tinymaix | 10 | tm | tm | 0 | 0 |
| toks | 436 | toks | toks | 0 | 3 |
| usockets | 118 | us | us | 0 | 0 |
| vlfeat | 353 | vl | vl | 0 | 0 |
| voxtral.c | 85 | vox | vox | 0 | 0 |
| wob | 9 | wob | wob | 0 | 0 |
| xxhash | 62 | xxh3 | xxh3 | 0 | 0 |
| yajl | 12 | yajl | yajl | 0 | 0 |
| yara | 491 | yr | yr | 0 | 1 |
| yyjson | 62 | yyjson | yyjson | 0 | 0 |
| zerocast | 9 | zerocast | zerocast | 0 | 0 |
| zlog | 233 | zlog | zlog | 0 | 0 |
| zstd | 1034 | zstd | zstd | 0 | 0 |

Tabloda olmayan 198 projede iki kural da önek bulmuyor.

## Örnekler (gerçek ad → siklik kuralıyla hedef)

- **catime** (1606/1640): `ma__is_channel_map_valid` → `_is_channel_map_valid`, `ma__malloc_default` → `_malloc_default`, `ma__realloc_default` → `_realloc_default`, `ma_aligned_free` → `aligned_free`, `ma_aligned_malloc` → `aligned_malloc`, `ma_allocate_AudioBufferList__coreaudio` → `allocate_AudioBufferList__coreaudio`
- **ttgo_twatch_library** (1115/1738): `lv_anim_count_running` → `anim_count_running`, `lv_anim_del` → `anim_del`, `lv_anim_del_all` → `anim_del_all`, `lv_anim_get` → `anim_get`, `lv_anim_init` → `anim_init`, `lv_anim_path_bounce` → `anim_path_bounce`
- **cglm** (712/728): `glmc_aabb2d_aabb` → `aabb2d_aabb`, `glmc_aabb2d_center` → `aabb2d_center`, `glmc_aabb2d_circle` → `aabb2d_circle`, `glmc_aabb2d_contains` → `aabb2d_contains`, `glmc_aabb2d_copy` → `aabb2d_copy`, `glmc_aabb2d_crop` → `aabb2d_crop`
- **wasm3** (685/1273): `Op_ContinueLoop` → `ContinueLoop`, `op_AtomicCmpxchg` → `AtomicCmpxchg`, `op_AtomicLoad` → `AtomicLoad`, `op_AtomicNotify` → `AtomicNotify`, `op_AtomicRmw` → `AtomicRmw`, `op_AtomicStore` → `AtomicStore`
- **php-ext-xlswriter** (589/1525): `lxlsx_add_document_relationship` → `add_document_relationship`, `lxlsx_add_drawing_object` → `add_drawing_object`, `lxlsx_add_ms_package_relationship` → `add_ms_package_relationship`, `lxlsx_add_package_relationship` → `add_package_relationship`, `lxlsx_add_rich_value_relationship` → `add_rich_value_relationship`, `lxlsx_add_worksheet_relationship` → `add_worksheet_relationship`
- **cmsis-dsp** (557/563): `arm_abs_f32` → `abs_f32`, `arm_abs_f64` → `abs_f64`, `arm_abs_q15` → `abs_q15`, `arm_abs_q31` → `abs_q31`, `arm_abs_q7` → `abs_q7`, `arm_absmax_f32` → `absmax_f32`
- **kha** (426/694): `hl_add_root` → `add_root`, `hl_alloc_array` → `alloc_array`, `hl_alloc_buffer` → `alloc_buffer`, `hl_alloc_bytes` → `alloc_bytes`, `hl_alloc_carray` → `alloc_carray`, `hl_alloc_closure_ptr` → `alloc_closure_ptr`
- **sqlcipher** (407/619): `JimAddMulHelper` → `AddMulHelper`, `JimAddStackFrame` → `AddStackFrame`, `JimAioDelProc` → `AioDelProc`, `JimAioErrorString` → `AioErrorString`, `JimAioOpenCommand` → `AioOpenCommand`, `JimAioPipeCommand` → `AioPipeCommand`
- **ziparchive** (328/387): `mz_crypt_aes_create` → `crypt_aes_create`, `mz_crypt_aes_delete` → `crypt_aes_delete`, `mz_crypt_aes_encrypt` → `crypt_aes_encrypt`, `mz_crypt_aes_encrypt_final` → `crypt_aes_encrypt_final`, `mz_crypt_aes_free` → `crypt_aes_free`, `mz_crypt_aes_reset` → `crypt_aes_reset`
- **lcui** (322/955): `ui_apply_column_item_main_size` → `apply_column_item_main_size`, `ui_apply_row_item_main_size` → `apply_row_item_main_size`, `ui_block_layout_apply_width` → `block_layout_apply_width`, `ui_block_layout_load_width` → `block_layout_load_width`, `ui_block_layout_next_row` → `block_layout_next_row`, `ui_block_layout_reflow` → `block_layout_reflow`
- **jerryscript** (299/449): `ecma_alloc_extended_string` → `alloc_extended_string`, `ecma_alloc_external_string` → `alloc_external_string`, `ecma_alloc_number` → `alloc_number`, `ecma_alloc_property_pair` → `alloc_property_pair`, `ecma_big_uint_add` → `big_uint_add`, `ecma_big_uint_bitwise_op` → `big_uint_bitwise_op`
- **lovr** (251/480): `ma_allocate_AudioBufferList__coreaudio` → `allocate_AudioBufferList__coreaudio`, `ma_audio_buffer_config_init` → `audio_buffer_config_init`, `ma_audio_buffer_init_ex` → `audio_buffer_init_ex`, `ma_audio_buffer_ref_init` → `audio_buffer_ref_init`, `ma_audio_buffer_ref_read_pcm_frames` → `audio_buffer_ref_read_pcm_frames`, `ma_biquad_config_init` → `biquad_config_init`
- **libsodium** (236/597): `crypto_aead_aegis128l_abytes` → `aead_aegis128l_abytes`, `crypto_aead_aegis128l_decrypt` → `aead_aegis128l_decrypt`, `crypto_aead_aegis128l_decrypt_detached` → `aead_aegis128l_decrypt_detached`, `crypto_aead_aegis128l_encrypt` → `aead_aegis128l_encrypt`, `crypto_aead_aegis128l_encrypt_detached` → `aead_aegis128l_encrypt_detached`, `crypto_aead_aegis128l_keybytes` → `aead_aegis128l_keybytes`
- **lunasvg** (226/399): `plutovg_blend` → `blend`, `plutovg_blend_color` → `blend_color`, `plutovg_blend_gradient` → `blend_gradient`, `plutovg_blend_texture` → `blend_texture`, `plutovg_canvas_add_font_face` → `canvas_add_font_face`, `plutovg_canvas_add_font_file` → `canvas_add_font_file`
- **eth.zig** (199/494): `secp256k1_callback_call` → `callback_call`, `secp256k1_context_clone` → `context_clone`, `secp256k1_context_create` → `context_create`, `secp256k1_context_destroy` → `context_destroy`, `secp256k1_context_preallocated_clone` → `context_preallocated_clone`, `secp256k1_context_preallocated_clone_size` → `context_preallocated_clone_size`
- **bare-metal-programming-guide** (188/279): `mg_alloc_conn` → `alloc_conn`, `mg_atod` → `atod`, `mg_aton` → `aton`, `mg_aton4` → `aton4`, `mg_aton6` → `aton6`, `mg_atone` → `atone`
- **catimg** (186/219): `stbi__YCbCr_to_RGB_row` → `_YCbCr_to_RGB_row`, `stbi__YCbCr_to_RGB_simd` → `_YCbCr_to_RGB_simd`, `stbi__addints_valid` → `_addints_valid`, `stbi__addsizes_valid` → `_addsizes_valid`, `stbi__at_eof` → `_at_eof`, `stbi__bit_reverse` → `_bit_reverse`
- **libpostal** (155/498): `cmp_init` → `init`, `cmp_mp_version` → `mp_version`, `cmp_object_as_array` → `object_as_array`, `cmp_object_as_bin` → `object_as_bin`, `cmp_object_as_bool` → `object_as_bool`, `cmp_object_as_char` → `object_as_char`
- **warp** (147/382): `waste__bind_self` → `_bind_self`, `waste__env_spin` → `_env_spin`, `waste__env_spin_slow` → `_env_spin_slow`, `waste__pool_run` → `_pool_run`, `waste__worker` → `_worker`, `waste_act_pair_range` → `act_pair_range`
- **quickjs** (145/287): `JS_AtomToCString` → `AtomToCString`, `JS_IsBigInt` → `IsBigInt`, `JS_IsBool` → `IsBool`, `JS_IsException` → `IsException`, `JS_IsModule` → `IsModule`, `JS_IsNull` → `IsNull`
- **mcuboot** (137/171): `zcbor_any_skip` → `any_skip`, `zcbor_array_at_end` → `array_at_end`, `zcbor_bool_decode` → `bool_decode`, `zcbor_bool_encode` → `bool_encode`, `zcbor_bool_expect` → `bool_expect`, `zcbor_bool_pexpect` → `bool_pexpect`
- **onedraw** (122/157): `stbtt_BakeFontBitmap` → `BakeFontBitmap`, `stbtt_BakeFontBitmap_internal` → `BakeFontBitmap_internal`, `stbtt_CompareUTF8toUTF16_bigendian` → `CompareUTF8toUTF16_bigendian`, `stbtt_CompareUTF8toUTF16_bigendian_internal` → `CompareUTF8toUTF16_bigendian_internal`, `stbtt_FindGlyphIndex` → `FindGlyphIndex`, `stbtt_FindMatchingFont` → `FindMatchingFont`
- **barco** (114/164): `arg_basename` → `basename`, `arg_cat` → `cat`, `arg_cat_option` → `cat_option`, `arg_cat_optionv` → `cat_optionv`, `arg_cmd_count` → `cmd_count`, `arg_cmd_dispatch` → `cmd_dispatch`
- **jansson** (104/224): `json_array` → `array`, `json_array_append` → `array_append`, `json_array_append_new` → `array_append_new`, `json_array_clear` → `array_clear`, `json_array_copy` → `array_copy`, `json_array_deep_copy` → `array_deep_copy`
- **fcvvdp** (79/85): `cvvdp_alloc_float` → `alloc_float`, `cvvdp_apply_display_impl` → `apply_display_impl`, `cvvdp_apply_display_model` → `apply_display_model`, `cvvdp_apply_display_model_interleaved` → `apply_display_model_interleaved`, `cvvdp_apply_display_task` → `apply_display_task`, `cvvdp_baseband_diff_impl` → `baseband_diff_impl`
- **hash_extender** (60/110): `buffer_add_buffer` → `add_buffer`, `buffer_add_buffer_at` → `add_buffer_at`, `buffer_add_bytes` → `add_bytes`, `buffer_add_bytes_at` → `add_bytes_at`, `buffer_add_int16` → `add_int16`, `buffer_add_int16_at` → `add_int16_at`
- **wasm-micro-runtime** (58/64): `ocall_accept` → `accept`, `ocall_bind` → `bind`, `ocall_clock_getres` → `clock_getres`, `ocall_clock_gettime` → `clock_gettime`, `ocall_clock_nanosleep` → `clock_nanosleep`, `ocall_closedir` → `closedir`
- **chia-plotter** (55/139): `HUF_buildCTable` → `buildCTable`, `HUF_compress` → `compress`, `HUF_compress1X` → `compress1X`, `HUF_compress1X_repeat` → `compress1X_repeat`, `HUF_compress1X_usingCTable_internal` → `compress1X_usingCTable_internal`, `HUF_compress1X_usingCTable_internal_bmi2` → `compress1X_usingCTable_internal_bmi2`
- **arduino-mqtt** (49/49): `lwmqtt_connect` → `connect`, `lwmqtt_cycle_once` → `cycle_once`, `lwmqtt_cycle_until` → `cycle_until`, `lwmqtt_decode_ack` → `decode_ack`, `lwmqtt_decode_connack` → `decode_connack`, `lwmqtt_decode_publish` → `decode_publish`
- **gmssl** (46/46): `SKF_ChangePIN` → `ChangePIN`, `SKF_ConnectDev` → `ConnectDev`, `SKF_CreateApplication` → `CreateApplication`, `SKF_CreateContainer` → `CreateContainer`, `SKF_CreateFile` → `CreateFile`, `SKF_Digest` → `Digest`
- **shecc** (45/145): `a64_add_ext_insn` → `add_ext_insn`, `a64_add_imm_insn` → `add_imm_insn`, `a64_add_reg_insn` → `add_reg_insn`, `a64_adrp_pages_insn` → `adrp_pages_insn`, `a64_and_reg_insn` → `and_reg_insn`, `a64_asrv_insn` → `asrv_insn`
- **wax** (43/46): `yajl_alloc` → `alloc`, `yajl_buf_alloc` → `buf_alloc`, `yajl_buf_append` → `buf_append`, `yajl_buf_clear` → `buf_clear`, `yajl_buf_ensure_available` → `buf_ensure_available`, `yajl_buf_free` → `buf_free`
- **hactool** (38/111): `LZ4_NbCommonBytes` → `NbCommonBytes`, `LZ4_attach_dictionary` → `attach_dictionary`, `LZ4_compress` → `compress`, `LZ4_compressBound` → `compressBound`, `LZ4_compress_default` → `compress_default`, `LZ4_compress_destSize` → `compress_destSize`
- **easylogger** (36/42): `elog_async_deinit` → `async_deinit`, `elog_async_get_buf_used` → `async_get_buf_used`, `elog_async_get_line_log` → `async_get_line_log`, `elog_async_init` → `async_init`, `elog_async_output` → `async_output`, `elog_async_output_notice` → `async_output_notice`
- **arduino-homekit-esp8266** (32/57): `HOMEKIT_BOOL_CPP` → `BOOL_CPP`, `HOMEKIT_DATA_CPP` → `DATA_CPP`, `HOMEKIT_FLOAT_CPP` → `FLOAT_CPP`, `HOMEKIT_INT_CPP` → `INT_CPP`, `HOMEKIT_NULL_CPP` → `NULL_CPP`, `HOMEKIT_STRING_CPP` → `STRING_CPP`
- **blurhash** (27/62): `stbiw__crc32` → `_crc32`, `stbiw__encode_png_line` → `_encode_png_line`, `stbiw__fopen` → `_fopen`, `stbiw__jpg_DCT` → `_jpg_DCT`, `stbiw__jpg_calcBits` → `_jpg_calcBits`, `stbiw__jpg_processDU` → `_jpg_processDU`
- **wrk2** (27/74): `hdr_add` → `add`, `hdr_alloc` → `alloc`, `hdr_count_at_value` → `count_at_value`, `hdr_get_memory_size` → `get_memory_size`, `hdr_init` → `init`, `hdr_iter_init` → `iter_init`
- **sajs** (26/60): `eat_elem_first` → `elem_first`, `eat_elem_next` → `elem_next`, `eat_elem_sep` → `elem_sep`, `eat_false` → `false`, `eat_literal` → `literal`, `eat_mem_name_first` → `mem_name_first`
- **musializer** (25/28): `nob__cmd_start_process` → `_cmd_start_process`, `nob__go_rebuild_urself` → `_go_rebuild_urself`, `nob__proc_wait_async` → `_proc_wait_async`, `nob_cmd_run_async` → `cmd_run_async`, `nob_cmd_run_async_and_reset` → `cmd_run_async_and_reset`, `nob_cmd_run_async_redirect` → `cmd_run_async_redirect`
- **tinyusb** (23/63): `SEGGER_RTT_AllocDownBuffer` → `RTT_AllocDownBuffer`, `SEGGER_RTT_AllocUpBuffer` → `RTT_AllocUpBuffer`, `SEGGER_RTT_ConfigDownBuffer` → `RTT_ConfigDownBuffer`, `SEGGER_RTT_ConfigUpBuffer` → `RTT_ConfigUpBuffer`, `SEGGER_RTT_GetAvailWriteSpace` → `RTT_GetAvailWriteSpace`, `SEGGER_RTT_HasData` → `RTT_HasData`
- **how-to-make-a-computer-operating-system** (19/29): `trio_duplicate_max` → `duplicate_max`, `trio_equal_locale` → `equal_locale`, `trio_format_date_max` → `format_date_max`, `trio_index` → `index`, `trio_lower` → `lower`, `trio_string_contains` → `string_contains`
- **nature** (19/34): `ld_elf_eh_frame_hdr_compare_entries` → `elf_eh_frame_hdr_compare_entries`, `ld_elf_eh_frame_hdr_encode` → `elf_eh_frame_hdr_encode`, `ld_elf_eh_frame_hdr_relative_i32` → `elf_eh_frame_hdr_relative_i32`, `ld_elf_eh_frame_hdr_result_string` → `elf_eh_frame_hdr_result_string`, `ld_elf_eh_frame_hdr_size` → `elf_eh_frame_hdr_size`, `ld_elf_rel_aarch64_adr` → `elf_rel_aarch64_adr`
- **haywire** (16/47): `http_errno_description` → `errno_description`, `http_errno_name` → `errno_name`, `http_parser_parse_url` → `parser_parse_url`, `http_parser_pause` → `parser_pause`, `http_parser_version` → `parser_version`, `http_request_buffer_alloc` → `request_buffer_alloc`
- **sslsplit** (15/42): `logger_close` → `close`, `logger_free` → `free`, `logger_join` → `join`, `logger_leave` → `leave`, `logger_new` → `new`, `logger_open` → `open`
- **wlipsync** (15/35): `PT_cosf` → `cosf`, `PT_exp2f` → `exp2f`, `PT_expf` → `expf`, `PT_fabsf` → `fabsf`, `PT_floor` → `floor`, `PT_floorf` → `floorf`
- **ixy** (14/30): `virtio_get_link_speed` → `get_link_speed`, `virtio_init` → `init`, `virtio_legacy_check_status` → `legacy_check_status`, `virtio_legacy_init` → `legacy_init`, `virtio_legacy_notify_queue` → `legacy_notify_queue`, `virtio_legacy_set_promiscuous` → `legacy_set_promiscuous`
- **p2pvc** (14/38): `PaUtil_AdvanceRingBufferReadIndex` → `AdvanceRingBufferReadIndex`, `PaUtil_AdvanceRingBufferWriteIndex` → `AdvanceRingBufferWriteIndex`, `PaUtil_DebugPrint` → `DebugPrint`, `PaUtil_FlushRingBuffer` → `FlushRingBuffer`, `PaUtil_Generate16BitTriangularDither` → `Generate16BitTriangularDither`, `PaUtil_GenerateFloatTriangularDither` → `GenerateFloatTriangularDither`
- **stratux** (14/42): `uat_decode_adsb_mdb` → `decode_adsb_mdb`, `uat_decode_auxsv` → `decode_auxsv`, `uat_decode_hdr` → `decode_hdr`, `uat_decode_ms` → `decode_ms`, `uat_decode_sv` → `decode_sv`, `uat_decode_uplink_mdb` → `decode_uplink_mdb`
- **craft** (13/29): `ring_alloc` → `alloc`, `ring_empty` → `empty`, `ring_free` → `free`, `ring_full` → `full`, `ring_get` → `get`, `ring_grow` → `grow`
- **fzy** (12/16): `choices_add` → `add`, `choices_destroy` → `destroy`, `choices_fread` → `fread`, `choices_get` → `get`, `choices_getscore` → `getscore`, `choices_init` → `init`
- **ios-webkit-debug-proxy** (12/35): `ht_clear` → `clear`, `ht_find` → `find`, `ht_free` → `free`, `ht_get` → `get`, `ht_get_all` → `get_all`, `ht_get_key` → `get_key`
- **microcheck** (12/26): `http_base64_encode` → `base64_encode`, `http_free_build_request_result` → `free_build_request_result`, `http_free_header` → `free_header`, `http_free_headers` → `free_headers`, `http_get_response_status_code` → `get_response_status_code`, `http_headers_add_header` → `headers_add_header`
- **tilck** (12/25): `term_alt_buffer_enter` → `alt_buffer_enter`, `term_alt_buffer_exit` → `alt_buffer_exit`, `term_clear` → `clear`, `term_cursor_enable` → `cursor_enable`, `term_draw_rect_labeled` → `draw_rect_labeled`, `term_draw_rect_raw` → `draw_rect_raw`
- **zclaw** (12/32): `telegram_chat_ids_contains` → `chat_ids_contains`, `telegram_chat_ids_parse` → `chat_ids_parse`, `telegram_chat_ids_resolve_target` → `chat_ids_resolve_target`, `telegram_extract_bot_id` → `extract_bot_id`, `telegram_extract_max_update_id` → `extract_max_update_id`, `telegram_poll_timeout_for_backend` → `poll_timeout_for_backend`
- **photoc** (11/23): `review_base64_encode` → `base64_encode`, `review_base64_encode_bytes` → `base64_encode_bytes`, `review_iterm_auto_supported` → `iterm_auto_supported`, `review_iterm_render` → `iterm_render`, `review_iterm_render_bytes` → `iterm_render_bytes`, `review_terminal_enter` → `terminal_enter`
- **amx** (10/23): `emulate_AMX_GENLUT` → `AMX_GENLUT`, `emulate_AMX_LDX` → `AMX_LDX`, `emulate_AMX_LDY` → `AMX_LDY`, `emulate_AMX_LDZ` → `AMX_LDZ`, `emulate_AMX_LDZI` → `AMX_LDZI`, `emulate_AMX_MAC16` → `AMX_MAC16`
- **esp-homekit** (10/24): `mdns_print_answer` → `print_answer`, `mdns_print_hex` → `print_hex`, `mdns_print_name` → `print_name`, `mdns_print_packet` → `print_packet`, `mdns_print_pstr` → `print_pstr`, `mdns_print_question` → `print_question`
- **traildb** (10/21): `pqueue_change_priority` → `change_priority`, `pqueue_free` → `free`, `pqueue_init` → `init`, `pqueue_insert` → `insert`, `pqueue_peek` → `peek`, `pqueue_pop` → `pop`
- **ctypes.sh** (9/24): `rb_erase` → `erase`, `rb_first` → `first`, `rb_insert_color` → `insert_color`, `rb_last` → `last`, `rb_next` → `next`, `rb_prev` → `prev`
- **dperf** (9/10): `config_get_string` → `get_string`, `config_keyword_call` → `keyword_call`, `config_keyword_check_input` → `keyword_check_input`, `config_keyword_help` → `keyword_help`, `config_keyword_lookup` → `keyword_lookup`, `config_keyword_parse` → `keyword_parse`
- **easyhook** (7/9): `ud_asmprintf` → `asmprintf`, `ud_syn_print_addr` → `syn_print_addr`, `ud_syn_print_imm` → `syn_print_imm`, `ud_syn_print_mem_disp` → `syn_print_mem_disp`, `ud_syn_rel_target` → `syn_rel_target`, `ud_translate_att` → `translate_att`
- **i3** (7/7): `sd_is_fifo` → `is_fifo`, `sd_is_socket` → `is_socket`, `sd_is_socket_inet` → `is_socket_inet`, `sd_is_socket_internal` → `is_socket_internal`, `sd_is_socket_unix` → `is_socket_unix`, `sd_listen_fds` → `listen_fds`
- **libratbag** (7/13): `rbnode_black` → `black`, `rbnode_linked` → `linked`, `rbnode_next` → `next`, `rbnode_parent` → `parent`, `rbnode_prev` → `prev`, `rbnode_red` → `red`
- **picomatch** (7/21): `emit_arg` → `arg`, `emit_branch_end` → `branch_end`, `emit_exact` → `exact`, `emit_op` → `op`, `emit_quantifier` → `quantifier`, `emit_range_quantifier` → `range_quantifier`
- **raddebugger** (7/18): `sysv_default_func` → `default_func`, `sysv_hidden_func` → `hidden_func`, `sysv_ifunc_impl` → `ifunc_impl`, `sysv_internal_func` → `internal_func`, `sysv_protected_func` → `protected_func`, `sysv_run_all` → `run_all`
- **zipline** (7/9): `JS_AddGlobalThisGc` → `AddGlobalThisGc`, `JS_FreeValue` → `FreeValue`, `JS_IsNumber` → `IsNumber`, `JS_NewContextNoEval` → `NewContextNoEval`, `JS_SetProperty` → `SetProperty`, `jsFinalizerCollected` → `FinalizerCollected`
- **box64** (6/6): `log_TODO` → `TODO`, `log_error` → `error`, `log_internal` → `internal`, `log_memory` → `memory`, `log_warning` → `warning`, `loginfo_print` → `info_print`
- **cuik** (6/9): `tls_init` → `init`, `tls_pop` → `pop`, `tls_push` → `push`, `tls_reset` → `reset`, `tls_restore` → `restore`, `tls_save` → `save`
- **esp32** (5/8): `db_espnow_mavlink_parser_add_peer` → `espnow_mavlink_parser_add_peer`, `db_espnow_mavlink_parser_find_peer` → `espnow_mavlink_parser_find_peer`, `db_espnow_mavlink_parser_reset_rx` → `espnow_mavlink_parser_reset_rx`, `db_espnow_mavlink_parser_table_init` → `espnow_mavlink_parser_table_init`, `db_espnow_mavlink_parser_table_select` → `espnow_mavlink_parser_table_select`
- **google-authenticator-libpam** (5/12): `sha1_final` → `final`, `sha1_init` → `init`, `sha1_transform` → `transform`, `sha1_transform_and_copy` → `transform_and_copy`, `sha1_update` → `update`

## Çakışmalar (kırpma sonrası aynı hedef)

- ttgo_twatch_library: `fs_close` / `lv_fs_close`
- ttgo_twatch_library: `fs_dir_close` / `lv_fs_dir_close`
- ttgo_twatch_library: `fs_dir_open` / `lv_fs_dir_open`
- ttgo_twatch_library: `fs_dir_read` / `lv_fs_dir_read`
- ttgo_twatch_library: `fs_open` / `lv_fs_open`
- ttgo_twatch_library: `fs_read` / `lv_fs_read`
- ttgo_twatch_library: `fs_remove` / `lv_fs_remove`
- ttgo_twatch_library: `fs_rename` / `lv_fs_rename`
- ttgo_twatch_library: `fs_seek` / `lv_fs_seek`
- ttgo_twatch_library: `fs_size` / `lv_fs_size`
- ttgo_twatch_library: `fs_tell` / `lv_fs_tell`
- ttgo_twatch_library: `fs_trunc` / `lv_fs_trunc`
- ttgo_twatch_library: `fs_write` / `lv_fs_write`
- ttgo_twatch_library: `lv_theme_apply` / `theme_apply`
- wasm3: `Call` / `op_Call`
- wasm3: `Op_ContinueLoop` / `op_ContinueLoop`
- wasm3: `XXH64_digest` / `Xxh64_Digest`
- kha: `gc_major` / `hl_gc_major`
- sqlcipher: `DictAddElement` / `Jim_DictAddElement`
- sqlcipher: `JimCreateCommand` / `Jim_CreateCommand`
