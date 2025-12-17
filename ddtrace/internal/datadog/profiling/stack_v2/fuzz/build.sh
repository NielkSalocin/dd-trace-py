#!/bin/bash

TARGET=fuzz_echion_remote_read

echo "Building fuzz target: $TARGET"

cmake -S ddtrace/internal/datadog/profiling/stack_v2 -B /tmp/fuzz/build \
      -DBUILD_FUZZING=ON -DBUILD_TESTING=OFF -DSTACKV2_USE_LIBFUZZER=ON \
      -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined" \
      -DCMAKE_CXX_FLAGS="-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined" \
      -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined" \
  && cmake --build /tmp/fuzz/build -j --target $TARGET