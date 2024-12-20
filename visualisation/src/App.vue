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
  <!-- The Vue app main context -->
  <div id="app">
    <TheNavBar />
    <router-view ref="routerView" />
  </div>
</template>

<script lang="ts">
import Vue from 'vue';
import TheNavBar from "@/components/TheNavBar.vue";

export default Vue.extend({
  name: 'App',
  components: {TheNavBar},
});
</script>

<style>
#app {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
