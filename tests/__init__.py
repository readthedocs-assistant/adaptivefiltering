import adaptivefiltering
import contextlib
import os
import pytest


@contextlib.contextmanager
def mock_environment(**env):
    """Temporarily update the environment. Implementation taken from
    https://stackoverflow.com/questions/2059482/python-temporarily-modify-the-current-processs-environment/34333710
    """
    old_env = dict(os.environ)
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def _dataset_fixture(filename, spatial_reference=None):
    @pytest.fixture
    def _fixture():
        return adaptivefiltering.DataSet(filename, spatial_reference=spatial_reference)

    return _fixture


# Fixtures for the provided datasets
dataset = _dataset_fixture("500k_NZ20_Westport.laz")
minimal_dataset = _dataset_fixture("minimal.las", spatial_reference="EPSG:4326")


@pytest.fixture
def boundary_segmentation():
    return adaptivefiltering.segmentation.Segmentation(
        {
            "features": [
                {
                    "geometry": {
                        "coordinates": [
                            [
                                [8.705725083720136, 49.42308965603005],
                                [8.707155281693138, 49.423093286673364],
                                [8.70719283414031, 49.4231075567031],
                                [8.70718541147721, 49.4243549323965],
                                [8.706551800317948, 49.424360413763246],
                                [8.706526793019284, 49.42434617536664],
                                [8.706476609354468, 49.42434604799997],
                                [8.706451432959406, 49.42436015902981],
                                [8.705911958431617, 49.424358788345124],
                                [8.705886951319531, 49.424344549810485],
                                [8.705836767659251, 49.424344422166165],
                                [8.705799045163563, 49.42435850113913],
                                [8.70568638624683, 49.42431568966173],
                                [8.705680325255061, 49.424280236895314],
                                [8.705705501829526, 49.42426612603352],
                                [8.70566180317242, 49.424230577475726],
                                [8.705687064509279, 49.42420229189708],
                                [8.70566205754182, 49.4241880533137],
                                [8.705662651068081, 49.42408883026776],
                                [8.705687827549422, 49.42407471940917],
                                [8.705662820646415, 49.42406048082575],
                                [8.705688081894934, 49.42403219524591],
                                [8.705663075013408, 49.42401795666248],
                                [8.705663583745595, 49.42393290833498],
                                [8.705688844927863, 49.423904622754215],
                                [8.705745343422786, 49.42389767906303],
                                [8.705664007687247, 49.42386203472776],
                                [8.705664770778009, 49.42373446223257],
                                [8.705689947076984, 49.423720351372296],
                                [8.705665025140396, 49.42369193806687],
                                [8.705668501366063, 49.42311077443743],
                                [8.705725083720136, 49.42308965603005],
                            ]
                        ],
                        "type": "Polygon",
                    },
                    "properties": {
                        "style": {
                            "clickable": "false",
                            "color": "#add8e6",
                            "fill": "true",
                            "opacity": 0.5,
                            "stroke": "true",
                            "weight": 4,
                        }
                    },
                    "type": "Feature",
                }
            ],
            "type": "FeatureCollection",
        }
    )
