# python2mlir



### verifying with MLIR:
```sh
hlir-opt  -hlir-print-op-generic -allow-unregistered-dialect
```

### installing mlir on mac

brew install cmake ninja

git clone https://github.com/llvm/llvm-project.git
mkdir llvm-project/build
cd llvm-project/build

cmake -G Ninja ../llvm \
    -DLLVM_ENABLE_PROJECTS=mlir \
    -DLLVM_BUILD_EXAMPLES=ON \
    -DLLVM_TARGETS_TO_BUILD="AArch64" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_ENABLE_BINDINGS=OFF

cmake --build . --target check-mlir
cmake --build . --target install
