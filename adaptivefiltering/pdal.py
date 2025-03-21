from adaptivefiltering.asprs import asprs
from adaptivefiltering.dataset import DataSet
from adaptivefiltering.filter import Filter, PipelineMixin
from adaptivefiltering.paths import get_temporary_filename, load_schema, locate_file
from adaptivefiltering.segmentation import Segment, Segmentation, swap_coordinates
from adaptivefiltering.utils import (
    AdaptiveFilteringError,
    convert_Segmentation,
    check_spatial_reference,
    merge_segmentation_features,
)

from osgeo import ogr
import json
import os
import pdal
import pyrsistent


def execute_pdal_pipeline(dataset=None, config=None):
    """Execute a PDAL pipeline

    :param dataset:
        The :class:`~adaptivefiltering.DataSet` instance that this pipeline
        operates on. If :code:`None`, the pipeline will operate without inputs.
    :type dataset: :class:`~adaptivefiltering.DataSet`
    :param config:
        The configuration of the PDAL pipeline, according to the PDAL documentation.
    :type config: dict
    :return:
        The full pdal pipeline object
    :rtype: pipeline
    """
    # Make sure that a correct combination of arguments is given
    if config is None:
        raise ValueError("PDAL Pipeline configurations is required")

    # Undo stringification of the JSON to manipulate the pipeline
    if isinstance(config, str):
        config = json.loads(config)

    # Make sure that the JSON is a list of stages, even if just the
    # dictionary for a single stage was given
    if isinstance(config, dict):
        config = [config]

    # Construct the input array argument for the pipeline
    arrays = []
    if dataset is not None:
        arrays.append(dataset.data)

    # Define and execute the pipeline
    pipeline = pdal.Pipeline(json.dumps(config), arrays=arrays)
    _ = pipeline.execute()

    # We are currently only handling situations with one output array
    assert len(pipeline.arrays) == 1

    # Return the output pipeline
    return pipeline


class PDALFilter(Filter, identifier="pdal"):
    """A filter implementation based on PDAL"""

    def execute(self, dataset):
        dataset = PDALInMemoryDataSet.convert(dataset)
        config = pyrsistent.thaw(self.config)
        config.pop("_backend", None)
        return PDALInMemoryDataSet(
            pipeline=execute_pdal_pipeline(dataset=dataset, config=config),
            provenance=dataset._provenance
            + [f"Applying PDAL filter with the following configuration:\n{config}"],
        )

    @classmethod
    def schema(cls):
        return load_schema("pdal.json")

    def as_pipeline(self):
        return PDALPipeline(filters=[self])


class PDALPipeline(
    PipelineMixin, PDALFilter, identifier="pdal_pipeline", backend=False
):
    def execute(self, dataset):
        dataset = PDALInMemoryDataSet.convert(dataset)
        pipeline_json = pyrsistent.thaw(self.config["filters"])
        for f in pipeline_json:
            f.pop("_backend", None)

        return PDALInMemoryDataSet(
            pipeline=execute_pdal_pipeline(dataset=dataset, config=pipeline_json),
            provenance=dataset._provenance
            + [
                f"Applying PDAL pipeline with the following configuration:\n{pipeline_json}"
            ],
        )


class PDALInMemoryDataSet(DataSet):
    def __init__(self, pipeline=None, provenance=[], spatial_reference=None):
        """An in-memory implementation of a Lidar data set that can used with PDAL

        :param pipeline:
            The numpy representation of the data set. This argument is used by e.g. filters that
            already have the dataset in memory.
        :type data: pdal.pipeline
        """
        # Store the given data and provenance array
        self.pipeline = pipeline

        super(PDALInMemoryDataSet, self).__init__(
            provenance=provenance,
            spatial_reference=spatial_reference,
        )

    @property
    def data(self):
        return self.pipeline.arrays[0]

    @classmethod
    def convert(cls, dataset):
        """Covert a dataset to a PDALInMemoryDataSet instance.

        This might involve file system based operations.

        Warning: if no srs was specified and no comp_spatialreference entry is found in the metadata this function will exit with a Warning.

        :param dataset:
            The data set instance to convert.
        """
        # Conversion should be itempotent
        if isinstance(dataset, PDALInMemoryDataSet):
            return dataset

        # save spatial reference of dataset before it is lost
        spatial_reference = dataset.spatial_reference
        # If dataset is of unknown type, we should first dump it to disk
        dataset = dataset.save(get_temporary_filename("las"))

        # Load the file from the given filename
        assert dataset.filename is not None

        filename = locate_file(dataset.filename)

        # Execute the reader pipeline
        config = {"type": "readers.las", "filename": filename}
        if spatial_reference is not None:
            config["override_srs"] = spatial_reference
            config["nosrs"] = True

        pipeline = execute_pdal_pipeline(config=[config])

        if spatial_reference is None:
            spatial_reference = json.loads(pipeline.metadata)["metadata"][
                "readers.las"
            ]["comp_spatialreference"]

        spatial_reference = check_spatial_reference(spatial_reference)
        return PDALInMemoryDataSet(
            pipeline=pipeline,
            provenance=dataset._provenance
            + [f"Loaded {pipeline.arrays[0].shape[0]} points from {filename}"],
            spatial_reference=spatial_reference,
        )

    def save(self, filename, compress=False, overwrite=False):
        # Check if we would overwrite an input file
        if not overwrite and os.path.exists(filename):
            raise AdaptiveFilteringError(
                f"Would overwrite file '{filename}'. Set overwrite=True to proceed"
            )

        # Form the correct configuration string for compression
        compress = "laszip" if compress else "none"

        # Exectute writer pipeline
        execute_pdal_pipeline(
            dataset=self,
            config={
                "filename": filename,
                "type": "writers.las",
                "compression": compress,
            },
        )

        # Wrap the result in a DataSet instance
        return DataSet(
            filename=filename,
            spatial_reference=self.spatial_reference,
        )

    def restrict(self, segmentation=None):
        # If a single Segment is given, we convert it to a segmentation

        if isinstance(segmentation, Segment):
            segmentation = Segmentation([segmentation.__geo_interface__])

        def apply_restriction(seg):

            # not yet sure why the swap is necessary
            seg = swap_coordinates(seg)
            # convert the segmentation from EPSG:4326 to the spatial reference of the dataset
            seg = convert_Segmentation(seg, self.spatial_reference)

            # if multiple polygons have been selected they will be merged in one multipolygon
            # this guarentees, that len(seg[features]) is always 1.
            seg = merge_segmentation_features(seg)
            # Construct a WKT Polygon for the clipping
            # this will be either a single polygon or a multipolygon
            polygons = ogr.CreateGeometryFromJson(str(seg["features"][0]["geometry"]))
            polygons_wkt = polygons.ExportToWkt()

            from adaptivefiltering.pdal import execute_pdal_pipeline

            # Apply the cropping filter with all polygons
            newdata = execute_pdal_pipeline(
                dataset=self, config={"type": "filters.crop", "polygon": polygons_wkt}
            )

            return PDALInMemoryDataSet(
                pipeline=newdata,
                provenance=self._provenance
                + [
                    f"Cropping data to only include polygons defined by:\n{str(polygons)}"
                ],
                spatial_reference=self.spatial_reference,
            )

        # Maybe create the segmentation
        if segmentation is None:
            from adaptivefiltering.apps import create_segmentation

            restricted = create_segmentation(self)
            restricted._finalization_hook = apply_restriction

            return restricted
        else:
            return apply_restriction(segmentation)
