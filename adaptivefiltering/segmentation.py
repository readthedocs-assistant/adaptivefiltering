from adaptivefiltering.paths import load_schema
from adaptivefiltering.utils import AdaptiveFilteringError
from adaptivefiltering.dataset import DataSet
import geojson
import jsonschema
import ipyleaflet
import ipywidgets
import pdal
import json
import numpy as np


class Segment:
    def __init__(self, polygon, metadata={}):
        self.polygon = geojson.Polygon(polygon)
        self.metadata = metadata

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, _metadata):
        # Validate against our segment metadata schema
        schema = load_schema("segment_metadata.json")
        jsonschema.validate(instance=_metadata, schema=schema)
        self._metadata = _metadata

    @property
    def __geo_interface__(self):
        return {
            "type": "Feature",
            "geometry": self.polygon,
            "properties": self.metadata,
        }


class Segmentation(geojson.FeatureCollection):
    @classmethod
    def load(cls, filename):
        """Load segmentation from a filename

        :param filename:
            The filename to load from. Relative paths are interpreted
            w.r.t. the current working directory.
        :type filename: str
        """
        with open(filename, "r") as f:
            return Segmentation(geojson.load(f))

    def save(self, filename):
        """Save the segmentation to disk

        :param filename:
            The filename to save the segmentation to. Relative paths are interpreted
            w.r.t. the current working directory.
        :type filename: str
        """
        with open(filename, "w") as f:
            geojson.dump(self, f)

    def show(self):
        """This will create a new InteractiveMap with bounds from the segmentation.
             use
                 map = self.show()
                 map
             to show and access the data of the new map or just
                self.show() to show the map without interacting with it.
        :param grid:
             The grid object which holds the map and the right side interface
         :type grid: ipyleaflet.grid
        """

        segmentation_map = InteractiveMap(segmentation=self)
        return segmentation_map.show()

    @property
    def __geo_interface__(self):
        return {
            "type": "FeatureCollection",
            "features": self.features,
        }


class InteractiveMap:
    def __init__(self, dataset=None, segmentation=None):
        """This class manages the interactive map on which one can choose the segmentation.
            It can be initilized with a dataset from which it will detect the boundaries and show them on the map.
            Or it can be initilized with a segmentation which will also be visualized on the map.
            There can be multiple polygons in the Segmentation and all will drawn. The


        :param dataset:
            The dataset from which the map should be displayed. This needs to be in a valid georeferenced format. Eg.: EPSG:4326
        :type dataset: Dataset
        :param segmentation:
            A premade segmentation can can be loaded and shown on a map without the need to load a dataset.
        :type segmentation: Segmentation

        """

        # handle exeptions
        from adaptivefiltering.pdal import PDALInMemoryDataSet

        if dataset and segmentation:
            raise Exception(
                "A dataset and a segmentation can't be loaded at the same time."
            )

        if dataset is None and segmentation["features"] == []:
            raise Exception("an empty segmention was given.")

        if dataset is None and segmentation is None:
            # if no dataset or segmentation is given, the map will be centered at the SSC office
            self.coordinates_mean = np.asarray([49.41745, 8.67529])
            self.segmentation = None

        if dataset is not None and not isinstance(
            dataset, (DataSet, PDALInMemoryDataSet)
        ):
            raise TypeError(
                "Dataset must be of type DataSet, but is " + str(type(dataset))
            )

        # prepare the map data

        # if a dataset is given the boundry of the data set is calculated via the hexbin function
        # and the in memory dataset is converted into EPSG:4326.
        if dataset and segmentation is None:
            self.segmentation = self.get_boundary(dataset)

        elif dataset is None and segmentation:
            self.segmentation = segmentation

        # setup ipyleaflet GeoJSON object
        boundary_coordinates = self.segmentation["features"][0]["geometry"][
            "coordinates"
        ]
        self.coordinates_mean = np.mean(np.squeeze(boundary_coordinates), axis=0)
        self.boundary_geoJSON = ipyleaflet.GeoJSON(data=self.segmentation)
        # for ipleaflet we need to change the order of the center coordinates

        print(self.coordinates_mean)
        self.m = ipyleaflet.Map(
            basemap=ipyleaflet.basemaps.Esri.WorldImagery,
            center=(self.coordinates_mean[1], self.coordinates_mean[0]),
            crs=ipyleaflet.projections.EPSG3857,
            scroll_wheel_zoom=True,
            max_zoom=20,
        )
        self.m.add_layer(self.boundary_geoJSON)

        # add polygon draw tool and zoom slider
        self.add_zoom_slider()
        self.add_polygon_control()

        # setup the grid with a list of widgets
        self.setup_grid([self.m])

    def get_boundary(self, dataset):
        """Takes the boundry coordinates of the  given dataset
            through the pdal hexbin filter and returns them as a segmentation.

        :param dataset:
            The dataset from which the map should be displayed.
            This needs to be in a valid georeferenced format. Eg.: EPSG:4326
        :type dataset: Dataset

        :return:
        :param hexbin_segmentation:
            The Segmentation of the area from the dataset
        :type hexbin_segmentation: Segmentation

        """
        from adaptivefiltering.pdal import execute_pdal_pipeline, PDALInMemoryDataSet

        # convert dataset to in memory pdal dataset
        dataset = PDALInMemoryDataSet.convert(dataset)

        # convert the dataset to EPSG:4326 format
        # dataset = dataset.convert_georef(spatial_ref_out="EPSG:4326")

        # execute the reprojection and hexbin filter.
        # this is nessesary for the map to function properly.
        hexbin_pipeline = execute_pdal_pipeline(
            dataset=dataset,
            config=[
                {"type": "filters.hexbin"},
            ],
        )

        # get the coordinates from the metadata:
        # this gives us lat, lon but for geojson we need lon, lat
        coordinates = json.loads(hexbin_pipeline.metadata)["metadata"][
            "filters.hexbin"
        ]["boundary_json"]["coordinates"]

        # set up the segnemtation object to later load into the map
        hexbin_segmentation = Segmentation(
            [
                {
                    "type": "Feature",
                    "properties": {
                        "style": {
                            "stroke": True,
                            "color": "#add8e6",
                            "weight": 4,
                            "opacity": 0.5,
                            "fill": True,
                            "fillColor": "#add8e6",
                            "fillOpacity": 0.1,
                            "clickable": True,
                        }
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": coordinates,
                    },
                }
            ]
        )
        # flip the coordinates to reflect proper geojson format
        # hexbin_segmentation["features"][0]["geometry"]["coordinates"] = np.flip(
        #     np.asarray(hexbin_segmentation["features"][0]["geometry"]["coordinates"])
        # ).tolist()

        return hexbin_segmentation

    def add_zoom_slider(self):
        """Adds the zoom slider to the interactive map.
        Also sets the default zoom.
        """

        self.zoom_slider = ipywidgets.IntSlider(
            description="Zoom level:", min=0, max=20, value=16
        )
        ipywidgets.jslink((self.zoom_slider, "value"), (self.m, "zoom"))
        self.zoom_control1 = ipyleaflet.WidgetControl(
            widget=self.zoom_slider, position="topright"
        )
        self.m.add_control(self.zoom_control1)

    def add_polygon_control(self):
        """Adds the polygon draw control."""
        self.draw_control = ipyleaflet.DrawControl(
            layout=ipywidgets.Layout(width="auto", grid_area="main")
        )
        # deactivate polyline and circlemarker
        self.draw_control.polyline = {}
        self.draw_control.circlemarker = {}

        self.draw_control.polygon = {
            "shapeOptions": {
                "fillColor": "black",
                "color": "black",
                "fillOpacity": 0.1,
            },
            "drawError": {"color": "#dd253b", "message": "Oups!"},
            "allowIntersection": False,
        }

        self.m.add_control(self.draw_control)

    def setup_grid(self, objects):
        """
        Setup the grid layout to allow the color bar and
        more on the right side of the map.
        """
        self.grid = ipywidgets.GridBox(
            children=objects,
            layout=ipywidgets.Layout(
                width="100%",
                grid_template_columns="70% 30%",
                grid_template_areas="""
                        "main sidebar "
                    """,
            ),
        )

    def return_polygon(self):
        """Exports the current polygon list as a Segmentation object

        :return:
            :param segmentation:
                All current polygons in one segmentation object
            :type segmentation: Segmentation


        """

        segmentation = Segmentation(self.draw_control.data)
        return segmentation

    def load_polygon(self, segmentation):
        """imports a segmentation object onto the map.
            The function also checks for doubles.

        :param segmentation:
            A segmentation object which is to be loaded.
        :type segmentation: Segmentation

        """

        # save current polygon data
        current_data = self.draw_control.data

        # filters only new polygons. to avoid double entrys. Ignores color and style, only checks for the geometry.
        new_polygons = [
            new_polygon
            for new_polygon in segmentation["features"]
            if not new_polygon["geometry"]
            in [data["geometry"] for data in current_data]
        ]
        # adds the new polygons to the current data
        new_data = current_data + new_polygons
        self.draw_control.data = new_data

    def show(self):
        """This functions returns the grid object and makes the map visible.
        :param grid:
            The grid object which holds the map and the right side interface
        :type grid: ipyleaflet.grid
        """
        return self.grid
