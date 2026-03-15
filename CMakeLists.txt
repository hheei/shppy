cmake_minimum_required(VERSION 3.15)
project(Shppy LANGUAGES CXX)

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

# set(CMAKE_CXX_STANDARD 20)
# set(CMAKE_CXX_STANDARD_REQUIRED ON)

# =====================================================================
# Common settings and options
# =====================================================================

set(EXTRA_COMPILE_OPTIONS "" CACHE STRING "Compiler flags from presets")

# =====================================================================
# Core library definition (shared between C++ and Python bindings)
# =====================================================================

add_library(core INTERFACE)
target_include_directories(core INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/src)

if(EXTRA_COMPILE_OPTIONS)
    target_compile_options(core INTERFACE ${EXTRA_COMPILE_OPTIONS})
endif()

if(SKBUILD)
    message(STATUS "\
    If you are a software developer, and this is your own package, then
    it is usually much more efficient to install the build dependencies
    in your environment once and use the following command that avoids
    a costly creation of a new virtual environment at every compilation:
    =====================================================================
    $ pip install nanobind scikit-build-core[pyproject]
    $ pip install --no-build-isolation -ve .
    =====================================================================
    You may optionally add -Ceditable.rebuild=true to auto-rebuild when
    the package is imported. Otherwise, you need to re-run the above
    after editing C++ files."
    )

    # =====================================================================
    # Python bindings (nanobind)
    # =====================================================================
    find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development.Module
                OPTIONAL_COMPONENTS Development.SABIModule)

    find_package(nanobind CONFIG REQUIRED)

    nanobind_add_module(_core STABLE_ABI NB_STATIC src/bindings.cpp)
    target_link_libraries(_core PRIVATE core)
    install(TARGETS _core LIBRARY DESTINATION shppy)
    
else()
    message(WARNING "SKBUILD for this project is needed. Please install through pip.")
endif()


