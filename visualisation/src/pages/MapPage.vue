<template>
  <!-- The page that shows the map for the Digital Twin -->
  <div class="map-page">
    <div class="map-page-inner">
      <div class="full-height">
        <div class="layers-side-bar">
          <div class="layers">
            <div class="search-bar">
              <div class="search-title">Layers</div>

              <input type="text" placeholder="Search" />
            </div>
          </div>
          <!-- Add in correct props from data -->
          <div class="toggles">
            <div
              class="title"
              v-for="(modelParamOptions, key) of allModelParameterOptions"
              :key="key"
            >
              <div class="checkbox"></div>
              <div class="toggle-title">
                {{ modelParamOptions.name }}
                <select
                  v-if="modelParamOptions.data"
                  v-model="selectedParameters[key]"
                >
                  <option
                    v-for="option of modelParamOptions.data"
                    :value="option"
                    :key="option"
                  >
                    {{ option }}
                  </option>
                </select>
              </div>
            </div>
          </div>
          <div class="general-scenario">
            <div class="header">Pollutant Source Modelling (MEDUSA)</div>
            <div
              class="title"
              v-for="(modelParamOptions, key) of allModelParameterOptions"
              :key="key"
            >
              <label>
                {{ modelParamOptions.name }}
                <select
                  v-if="modelParamOptions.data"
                  v-model="selectedParameters[key]"
                >
                  <option
                    v-for="option of modelParamOptions.data"
                    :value="option"
                    :key="option"
                  >
                    {{ option }}
                  </option>
                </select>
                <input
                  v-else
                  type="number"
                  v-model.number="selectedParameters[key]"
                  :min="modelParamOptions.min"
                  :max="modelParamOptions.max"
                />
              </label>
            </div>
            <div class="generate-icon">
              <h3>Generate Scenerio</h3>
            </div>
          </div>
        </div>
        <MapViewer
          :init-lat="otakaro.latitude"
          :init-long="otakaro.longitude"
          :init-height="8000"
          :cesium-access-token="env.cesiumApiToken"
          :data-sources="dataSources"
          :scenarios="scenarios"
          :scenario-options="selectedParameters"
          @task-posted="onTaskPosted"
          @task-completed="onTaskCompleted"
          @task-failed="onTaskFailed"
        />
        <img
          id="legend"
          alt="Legend graphic showing how colour relates to depth"
          src="@/assets/viridis_legend.png"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AxiosError } from "axios";
import * as Cesium from "cesium";
import type {
  Bbox,
  MapViewerDataSourceOptions,
  Scenario,
} from "geo-visualisation-components";
import { MapViewer } from "geo-visualisation-components";
import { reactive, ref } from "vue";

import { usePageTitlePrefix } from "./composables/title";

interface DataOption {
  data: (string | number)[];
  min?: never;
  max?: never;
}

interface RangeOption {
  min?: number;
  max?: number;
  data?: never;
}

type ParameterOption = { name: string } & (RangeOption | DataOption);

// Add page title prefix to webpage title
usePageTitlePrefix("Map");

// Start location
const otakaro = {
  latitude: -43.51758,
  longitude: 172.677106,
};

// Drop down menu options for selecting parameters
const allModelParameterOptions = {
  antecedentDryDays: {
    name: "Antecedent Dry Days",
    min: 0,
  },
  averageRainIntensity: {
    name: "Average Rain Intensity",
    min: 0,
  },
  eventDuration: {
    name: "Event Duration",
    min: 0,
  },
  rainfallPh: {
    name: "Rainfall pH",
    min: 0,
    max: 14,
  },
} as Record<string, ParameterOption>;

// Environment variables
const env = {
  cesiumApiToken: import.meta.env.VITE_CESIUM_ACCESS_TOKEN,
  geoserver: {
    host: import.meta.env.VITE_GEOSERVER_HOST,
    port: import.meta.env.VITE_GEOSERVER_PORT,
  },
  db: {
    name: import.meta.env.VITE_POSTGRES_DB,
  },
};

// Features to display on map
const dataSources = ref<MapViewerDataSourceOptions>({});
const scenarios = ref<Scenario[]>([]);

// Default selected options for parameters
const selectedParameters = reactive<Record<string, number | string>>({
  antecedentDryDays: 13,
  averageRainIntensity: 12,
  eventDuration: 10,
  rainfallPh: 12,
});

/**
 * When a task has been posted, loads building outlines for the bbox area.
 *
 * @param event The @task-posted event passed up from MapViewer
 */
async function onTaskPosted(event: { bbox: Bbox }) {
  // Wipe existing data sources while new ones are being loaded
  dataSources.value = {};
  const bbox = event.bbox;
  const geoJsonDataSources = await loadBuildingGeojson(bbox);
  dataSources.value = { geoJsonDataSources };
}

/**
 * When a task has been completed, loads building outlines with flood data and flood raster for the bbox area.
 *
 * @param event The @task-completed event passed up from MapViewer
 */
async function onTaskCompleted(event: { bbox: Bbox; floodModelId: number }) {
  const geoJsonDataSources = await loadBuildingGeojson(
    event.bbox,
    event.floodModelId,
  );
  const floodRasterProvider = await fetchFloodRaster(event.floodModelId);
  dataSources.value = {
    geoJsonDataSources,
    imageryProviders: [floodRasterProvider],
  };
}

/**
 * When a task fails, reset the data sources to blank map
 */
async function onTaskFailed(event: { err: AxiosError }) {
  dataSources.value = {};
  console.log(event);
}

/**
 * Creates ImageryProvider from geoserver WMS for the flood raster.
 *
 * @param model_output_id The id of the flood raster to fetch
 */
async function fetchFloodRaster(
  model_output_id: number,
): Promise<Cesium.WebMapServiceImageryProvider> {
  const wmsOptions = {
    url: `${env.geoserver.host}:${env.geoserver.port}/geoserver/${env.db.name}-dt-model-outputs/wms`,
    layers: `output_${model_output_id}`,
    parameters: {
      service: "WMS",
      format: "image/png",
      transparent: true,
      styles: "viridis_raster",
    },
  };
  return new Cesium.WebMapServiceImageryProvider(wmsOptions);
}

/**
 * Loads the geojson for the building outlines for a given area.
 * If scenarioId is provided, then it colours each building depending on flood status
 * @param bbox the bounding box of the area to load
 * @param scenarioId the flood model output id
 */
async function loadBuildingGeojson(
  bbox: Bbox,
  scenarioId = -1,
): Promise<Cesium.GeoJsonDataSource[]> {
  // Create geoserver url based on bbox and scenarioId
  const gsWorkspaceName = `${env.db.name}-buildings`;
  const buildingStatusUrl =
    `${env.geoserver.host}:${env.geoserver.port}/geoserver/` +
    `${gsWorkspaceName}/ows?service=WFS&version=1.0.0&request=GetFeature` +
    `&typeName=${gsWorkspaceName}%3Abuilding_flood_status` +
    `&outputFormat=application%2Fjson&srsName=EPSG:4326&viewparams=scenario:${scenarioId}` +
    `&cql_filter=bbox(geometry,${bbox.lng1},${bbox.lat1},${bbox.lng2},${bbox.lat2},'EPSG:4326')`;
  const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
    buildingStatusUrl,
    {
      strokeWidth: 3,
    },
  );

  const floodedStyle = new Cesium.PolygonGraphics({
    material: Cesium.Color.DARKRED,
    outlineColor: Cesium.Color.RED,
  });
  const nonFloodedStyle = new Cesium.PolygonGraphics({
    material: Cesium.Color.DARKGREEN,
    outlineColor: Cesium.Color.FORESTGREEN,
  });
  const unknownStyle = new Cesium.PolygonGraphics({
    material: Cesium.Color.DARKGOLDENROD,
    outlineColor: Cesium.Color.GOLDENROD,
  });

  // Add extrusion height and colour to each building
  const buildingEntities = floodBuildingDS.entities.values;
  for (const entity of buildingEntities) {
    // Base style for all polygons
    const polyGraphics = new Cesium.PolygonGraphics({
      extrudedHeight: 4,
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
    entity.polygon = polyGraphics;
  }

  return [floodBuildingDS];
}
</script>

<style>
#legend {
  position: absolute;
  bottom: 40px;
  right: 30px;
  height: 175px;
}
</style>
