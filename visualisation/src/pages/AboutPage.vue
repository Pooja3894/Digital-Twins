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
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <b-container fluid>
    <h3>Flood Resilience Digital Twin (FReDT)</h3>
    <p>
      This web application visualises and provides controls to the Digital Twin for Flood Resilience in New Zealand.
    </p>
    <p>&nbsp;</p>
    <hr>
    <h4>Source code</h4>
    <p>
      The source code for the app <a href="https://github.com/GeospatialResearch/Digital-Twins">can be obtained from
        GitHub here</a>.
    </p>
    <hr>
    <h4>App licence</h4>
    <p>
      The code license for this particular version of the code can be found on our
      <!-- Disabling eslint rule so that "." can show directly after link anchor. -->
      <!-- eslint-disable vue/singleline-html-element-content-newline -->
      <router-link :to="{ name: 'License'}">License Page</router-link>.
    </p>
  </b-container>
</template>

<script lang="ts">
import {RouterLink} from "vue-router";
import Vue from "vue";
import titleMixin from "@/mixins/title"

export default Vue.extend({
  name: "AboutPage",
  title: "About",
  components: {
    RouterLink,
  },
  mixins: [titleMixin],
});
</script>
