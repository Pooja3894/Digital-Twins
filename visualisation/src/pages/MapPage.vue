<!--Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau-->
<!--LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE-->

<!--This program is free software: you can redistribute it and/or modify-->
<!--it under the terms of the GNU Affero General Public License as-->
<!--published by the Free Software Foundation, either version 3 of the-->
<!--License, or (at your option) any later version.-->

<!--This program is distributed in the hope that it will be useful,-->
<!--but WITHOUT ANY WARRANTY; without even the implied warranty of-->
<!--MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the-->
<!--GNU Affero General Public License for more details.-->

<!--You should have received a copy of the GNU Affero General Public License-->
<!--along with this program.  If not, see <http://www.gnu.org/licenses/>.-->

<template>
  <!-- The page that shows the map for the Digital Twin -->
  <div class="full-height">
    <!--  Error messages  -->
    <div v-show="errorMessage" class="card">
      <h3>{{ errorMessage }}</h3>
    </div>
    <!-- Loading symbol -->
    <div v-show="isLoading" class="">
      <LoadingSpinner />
      <h2>Fetching parameter options</h2>
    </div>
    <!-- Model Input controls -->
    <div v-for="(column, key) of selectionOptions" :key="key">
      <label>{{ column.name }}
        <select v-if="column.data" v-model="selectedOption[key]">
          <option v-for="option of column.data" :value="option" :key="option">
            {{ option }}
          </option>
        </select>
        <RangeNumberInput
          v-if="column.min != null && column.max != null"
          v-model.number="selectedOption[key]"
          :min="column.min"
          :max="column.max"
        />
        <span v-if="!selectionValidations?.[key]">&#x274c;</span>
      </label>
    </div>
    <!-- Map  -->
    <MapViewer
      v-if="!errorMessage && !isLoading"
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :init-height="8000"
      :cesium-access-token="env.cesiumApiToken"
      :data-sources="dataSources"
      :scenarios="scenarios"
      :scenario-options="selectedOption"
      @task-posted="onTaskPosted"
      @task-completed="onTaskCompleted"
      @task-failed="onTaskFailed"
    />
    <img id="legend" alt="Legend graphic showing how colour relates to depth" src="viridis_legend.png">
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import * as Cesium from "cesium";
import {LoadingSpinner, MapViewer} from 'geo-visualisation-components/src/components';
import titleMixin from "@/mixins/title";
import {Bbox, MapViewerDataSourceOptions, Scenario} from "geo-visualisation-components/src/types";
import axios, {AxiosError} from "axios";
import RangeNumberInput from "@/components/RangeNumberInput.vue";


interface DataOption {
  data: (string | number | boolean)[]
  min?: never;
  max?: never;
}

interface RangeOption {
  min: number;
  max: number;
  data?: never;
}

type SelectionOption = { name: string } & (RangeOption | DataOption)

type FetchedSelectionOptions = {
  projectedYear: SelectionOption,
  sspScenario: SelectionOption,
  confidenceLevel: SelectionOption,
  addVerticalLandMovement: SelectionOption,
  percentile: SelectionOption,
}

export default Vue.extend({
  name: "MapPage",
  title: "Map",
  mixins: [titleMixin],
  components: {
    LoadingSpinner,
    MapViewer,
    RangeNumberInput,
  },
  data() {
    return {
      // Start location
      kaiapoi: {
        latitude: -43.380881,
        longitude: 172.655714
      },
      // Features to display on map
      dataSources: {} as MapViewerDataSourceOptions,
      scenarios: [] as Scenario[],
      backendScenarioOptions: null as Record<string, {
        min_year: number,
        max_year: number,
        ssp_scenarios: string[],
        percentiles: number[],
      }> | null,
      // Default selected options for parameters
      selectedOption: {
        projectedYear: 2050,
        sspScenario: 'SSP2-4.5',
        confidenceLevel: "medium",
        addVerticalLandMovement: true,
        percentile: 50,
      } as Record<keyof FetchedSelectionOptions, string | number | boolean>,
      // Environment variables
      env: {
        cesiumApiToken: process.env.VUE_APP_CESIUM_ACCESS_TOKEN,
        geoserver: {
          host: process.env.VUE_APP_GEOSERVER_HOST,
          port: process.env.VUE_APP_GEOSERVER_PORT
        },
        db: {
          name: process.env.VUE_APP_POSTGRES_DB
        }
      },
      // Error message to be displayed if there are any errors.
      errorMessage: "",
      // Flag to display a loading spinner.
      isLoading: true,
    }
  },

  async created() {
    await this.fetchScenarioOptions();
    this.isLoading = false;
  },

  computed: {
    /**
     * Object describing the valid values and the labels for each selection param depending on the current confidence level.
     */
    selectionOptions(): FetchedSelectionOptions | null {
      // SelectionOptions cannot be initialised until backendScenarioOptions is initialised
      if (this.backendScenarioOptions == null)
        return null;
      const selectedConfidenceLevel = this.selectedOption.confidenceLevel as string;
      // Gather the valid values depending on the current selected confidence level
      const validSelectionOptions = this.backendScenarioOptions[selectedConfidenceLevel];

      return {
        confidenceLevel: {
          name: "Confidence Level",
          data: Object.keys(this.backendScenarioOptions)
        },
        addVerticalLandMovement: {
          name: "Add Vertical Land Movement",
          data: [true, false]
        },
        sspScenario: {
          name: "SSP Scenario",
          data: validSelectionOptions.ssp_scenarios
        },
        projectedYear: {
          name: "Projected Year",
          min: validSelectionOptions.min_year,
          max: validSelectionOptions.max_year
        },
        percentile: {
          name: "Percentile",
          data: validSelectionOptions.percentiles
        },
      }
    },

    /**
     * Object containing booleans for whether each selected scenarioOption is valid.
     * Will be null until selectionOptions is initialised.
     */
    selectionValidations(): Record<keyof FetchedSelectionOptions, boolean> | null {
      // Type-hinting needs some help
      const selectionOptions = this.selectionOptions as FetchedSelectionOptions | null
      // Cannot have valid values until selectionOptions is initialised.
      if (selectionOptions == null) {
        return null;
      }

      // Validate each value against selectionOptions.
      const isYearValid = selectionOptions.projectedYear.min! <= this.selectedOption.projectedYear
        && this.selectedOption.projectedYear <= selectionOptions.projectedYear.max!;

      const isSspScenarioValid = selectionOptions.sspScenario.data!.includes(this.selectedOption.sspScenario);

      const isConfidenceValid =
        selectionOptions.confidenceLevel.data!.includes(this.selectedOption.confidenceLevel);

      const isAddVerticalValid =
        selectionOptions.addVerticalLandMovement.data!.includes(this.selectedOption.addVerticalLandMovement);

      const isPercentileValid = selectionOptions.percentile.data!.includes(this.selectedOption.percentile);

      return {
        projectedYear: isYearValid,
        sspScenario: isSspScenarioValid,
        confidenceLevel: isConfidenceValid,
        addVerticalLandMovement: isAddVerticalValid,
        percentile: isPercentileValid,
      }
    },
  },

  methods: {
    /**
     * Queries the backend for the distinct combinations of valid scenario options.
     */
    async fetchScenarioOptions() {
      try {
        const response = await axios.get(
          `${location.protocol}//${location.hostname}:5000/models/flood/parameters`,
          {timeout: 10000});
        // Store valid scenario options
        this.backendScenarioOptions = response.data;
      } catch (error: unknown) {
        const axiosError = error as AxiosError;
        if (axiosError.code === "ECONNABORTED") {
          // Timeout
          this.errorMessage = "Could not reach the backend. Please refresh the page to try again.";
        } else if (axiosError.response?.status === 503) {
          // Service Unavailable
          this.errorMessage = "Backend celery worker could not be reached. Please refresh the page to try again.";
        } else {
          // Unexpected or unknown error.
          this.isLoading = false;
          this.errorMessage = "An unexpected error occurred. Please refresh the page to try again.";
          throw error;
        }
      }
    },

    /**
     * When a task has been posted, loads building outlines for the bbox area.
     *
     * @param event The @task-posted event passed up from MapViewer
     */
    async onTaskPosted(event: { bbox: Bbox }) {
      // Wipe existing data sources while new ones are being loaded
      this.dataSources = {}
      const bbox = event.bbox
      const geoJsonDataSources = await this.loadBuildingGeojson(bbox)
      this.dataSources = {geoJsonDataSources}
    },
    /**
     * When a task has been completed, loads building outlines with flood data and flood raster for the bbox area.
     *
     * @param event The @task-completed event passed up from MapViewer
     */
    async onTaskCompleted(event: { bbox: Bbox, floodModelId: number }) {
      const geoJsonDataSources = await this.loadBuildingGeojson(event.bbox, event.floodModelId)
      const floodRasterProvider = await this.fetchFloodRaster(event.floodModelId)
      this.dataSources = {
        geoJsonDataSources,
        imageryProviders: [floodRasterProvider]
      }
    },
    /**
     * When a task fails, reset the data sources to blank map
     */
    async onTaskFailed(event: {err: AxiosError}) {
      this.dataSources = {};
      console.log(event)
    },
    /**
     * Creates ImageryProvider from geoserver WMS for the flood raster.
     *
     * @param model_output_id The id of the flood raster to fetch
     */
    async fetchFloodRaster(model_output_id: number): Promise<Cesium.WebMapServiceImageryProvider> {
      const wmsOptions = {
        url: `${this.env.geoserver.host}:${this.env.geoserver.port}/geoserver/${this.env.db.name}-dt-model-outputs/wms`,
        layers: `output_${model_output_id}`,
        parameters: {
          service: 'WMS',
          format: 'image/png',
          transparent: true,
          styles: 'viridis_raster'
        }
      };
      return new Cesium.WebMapServiceImageryProvider(wmsOptions);
    },
    /**
     * Loads the geojson for the building outlines for a given area.
     * If scenarioId is provided, then it colours each building depending on flood status
     * @param bbox the bounding box of the area to load
     * @param scenarioId the flood model output id
     */
    async loadBuildingGeojson(bbox: Bbox, scenarioId = -1): Promise<Cesium.GeoJsonDataSource[]> {
      // Create geoserver url based on bbox and scenarioId
      const gsWorkspaceName = `${this.env.db.name}-buildings`
      const buildingStatusUrl = `${this.env.geoserver.host}:${this.env.geoserver.port}/geoserver/`
        + `${gsWorkspaceName}/ows?service=WFS&version=1.0.0&request=GetFeature`
        + `&typeName=${gsWorkspaceName}%3Abuilding_flood_status`
        + `&outputFormat=application%2Fjson&srsName=EPSG:4326&viewparams=scenario:${scenarioId}`
        + `&cql_filter=bbox(geometry,${bbox.lng1},${bbox.lat1},${bbox.lng2},${bbox.lat2},'EPSG:4326')`
      const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
        buildingStatusUrl, {
          strokeWidth: 3,
        });

      const floodedStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKRED,
        outlineColor: Cesium.Color.RED
      });
      const nonFloodedStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKGREEN,
        outlineColor: Cesium.Color.FORESTGREEN
      });
      const unknownStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKGOLDENROD,
        outlineColor: Cesium.Color.GOLDENROD
      });

      // Add extrusion height and colour to each building
      const buildingEntities = floodBuildingDS.entities.values;
      for (const entity of buildingEntities) {
        // Base style for all polygons
        const polyGraphics = new Cesium.PolygonGraphics({
          extrudedHeight: 4
        });
        const isFlooded = entity.properties?.is_flooded?.getValue();
        // Apply different styles based on flood status
        if (isFlooded == null) {
          polyGraphics.merge(unknownStyle);
        } else if (isFlooded) {
          polyGraphics.merge(floodedStyle);
        } else {
          polyGraphics.merge(nonFloodedStyle);
        }
        if (entity.polygon != undefined) {
          polyGraphics.merge(entity.polygon);
        }
        entity.polygon = polyGraphics
      }

      return [floodBuildingDS];
    },
  }
});
</script>

<style>
#legend {
  position: absolute;
  bottom: 40px;
  right: 30px;
  height: 175px
}
</style>
