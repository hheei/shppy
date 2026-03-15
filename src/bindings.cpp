#include <nanobind/nanobind.h>
// #include <nanobind/ndarray.h>
// #include <nanobind/stl/string.h>

namespace nb = nanobind;

NB_MODULE(_core, m) {
    m.def("add_floats",
	    [](float x, float y) { return x + y; },
	    nb::arg("x"),
	    nb::arg("y"),
	    "Return the sum of two float numbers.");

    m.def("square",
	    [](float x) { return x * x; },
	    nb::arg("x"),
	    "Return the square value of a float number.");
}
