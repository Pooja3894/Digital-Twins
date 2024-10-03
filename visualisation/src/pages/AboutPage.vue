<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc. -->
  <div class="container-fluid">
    <h3>Ōtākaro Digital Twin</h3>
    <p>
      This web application visualises and provides controls to the Ōtākaro Digital Twin.
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
      <router-link :to="{ name: 'License'}">License Page</router-link>
      .
    </p>
  </div>
</template>
sdfhgdfh
<script setup lang="ts">
import {RouterLink} from "vue-router";
import {usePageTitlePrefix} from "./composables/title";

// Add page title prefix to webpage title
usePageTitlePrefix("About");
</script>
