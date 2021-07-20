from adaptivefiltering.opals import *

from . import dataset

import jsonschema
import pyrsistent
import pytest


# The list of implemented modules
_availableOpalsModules = [
    # "Cell",
    # "Grid",
    "RobFilter",
]


@pytest.mark.skipif(not opals_is_present(), reason="OPALS not found.")
def test_opals():
    # A filter that does not set a type should raise an error
    with pytest.raises(jsonschema.ValidationError):
        OPALSFilter()

    # Instantiate a filter
    f = OPALSFilter(type="RobFilter")

    # Make sure that the filter widget can be displayed
    widget = f.widget_form()

    # And that the filter can be reconstructed using the form data
    f2 = f.copy(**pyrsistent.thaw(widget.data))


@pytest.mark.skipif(not opals_is_present(), reason="OPALS not found.")
@pytest.mark.slow
@pytest.mark.parametrize("mod", _availableOpalsModules)
def test_default_filter_settings(mod, dataset):
    f = OPALSFilter(type=mod)

    dataset = f.execute(dataset)
