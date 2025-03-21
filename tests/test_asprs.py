from adaptivefiltering.asprs import *

import pytest


def test_asprs_classification():
    # Test __getitem__ of the asprs object
    assert asprs[42] == (42,)
    assert asprs["ground"] == (2,)
    assert asprs[42, 17] == (17, 42)
    assert asprs[42, "ground"] == (2, 42)
    assert asprs["low_vegetation", "ground"] == (2, 3)
    assert asprs["low_vegetation  ", " ground "] == (2, 3)
    assert asprs["low_vegetation,ground"] == (2, 3)
    assert asprs["  low_vegetation ,  ground"] == (2, 3)
    assert asprs[2:4] == (2, 3, 4)
    assert asprs[2:4:2] == (2, 4)
    assert asprs[:4] == (0, 1, 2, 3, 4)
    assert asprs[253:] == (253, 254, 255)
    assert len(asprs[:]) == 256

    # Erroneous input to asprs.__getitem__
    with pytest.raises(AdaptiveFilteringError):
        asprs["non-existing"]

    with pytest.raises(AdaptiveFilteringError):
        asprs[-1]

    with pytest.raises(AdaptiveFilteringError):
        asprs[256]

    # Test convenience functions
    for code in (2, 3, 4, 5, 6, 7, 9, 11):
        name = asprs_class_name(code)
        assert isinstance(name, str)
        assert asprs_class_code(name)[0] == code

    # Test erroneous input of convenience functions
    with pytest.raises(AdaptiveFilteringError):
        asprs_class_name(256)

    with pytest.raises(AdaptiveFilteringError):
        asprs_class_code("foobar")
